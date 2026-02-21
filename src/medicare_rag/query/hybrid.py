"""Hybrid retriever combining semantic and keyword (BM25) search with
cross-source diversification for improved recall.

Architecture
------------
1. **Semantic search** — Chroma similarity search (embedding-based).
2. **BM25 keyword search** — exact term matching over the same corpus.
3. **Reciprocal Rank Fusion (RRF)** — merges both ranked lists, weighting
   semantic and keyword results independently.
4. **Cross-source diversification** — ensures the final result set includes
   documents from multiple source types (IOM, MCD, codes) when the query
   spans topics that cross source boundaries.
"""

import logging
import re
import threading
from typing import Any

try:
    from rank_bm25 import BM25Okapi

    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False
    BM25Okapi = None

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from medicare_rag.config import (
    CROSS_SOURCE_MIN_PER_SOURCE,
    GET_META_BATCH_SIZE,
    HYBRID_KEYWORD_WEIGHT,
    HYBRID_SEMANTIC_WEIGHT,
    LCD_RETRIEVAL_K,
    MAX_QUERY_VARIANTS,
    RRF_K,
)
from medicare_rag.index.store import get_raw_collection
from medicare_rag.query.expand import detect_source_relevance, expand_cross_source_query
from medicare_rag.query.retriever import (
    apply_topic_summary_boost,
    expand_lcd_query,
    is_lcd_query,
)

logger = logging.getLogger(__name__)

_TOKENIZE_RE = re.compile(r"\w+")


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer for BM25 indexing."""
    return _TOKENIZE_RE.findall(text.lower())


class BM25Index:
    """Lazily-built, thread-safe BM25 index over documents in a Chroma collection.

    Staleness is detected only by document count (new documents added or
    removed). In-place content updates to existing chunks are not detected;
    use :meth:`force_rebuild` after re-ingesting changed content.
    Callers should use :meth:`ensure_built` which checks staleness and
    rebuilds only when needed.
    """

    def __init__(self) -> None:
        self._index: Any = None
        self._documents: list[Document] = []
        self._doc_count: int = -1
        self._lock = threading.Lock()

    def _needs_rebuild(self, current_count: int) -> bool:
        return self._index is None or current_count != self._doc_count

    def ensure_built(self, collection: Any) -> None:
        """Build or rebuild the index if the collection size has changed."""
        count = collection.count()
        if not self._needs_rebuild(count):
            return
        with self._lock:
            if not self._needs_rebuild(count):
                return
            self._build(collection)

    def force_rebuild(self, collection: Any) -> None:
        """Unconditionally rebuild the index. Use after re-ingesting content
        when document count is unchanged but chunk text has changed."""
        with self._lock:
            self._build(collection)

    def _build(self, collection: Any) -> None:
        if not _HAS_BM25:
            raise ImportError("rank-bm25 is required for BM25 indexing")

        all_docs: list[Document] = []
        offset = 0
        while True:
            batch = collection.get(
                include=["documents", "metadatas"],
                limit=GET_META_BATCH_SIZE,
                offset=offset,
            )
            ids = batch.get("ids") or []
            texts = batch.get("documents") or []
            metas = batch.get("metadatas") or []

            for i in range(len(ids)):
                text = texts[i] if i < len(texts) else ""
                meta = metas[i] if i < len(metas) else {}
                all_docs.append(Document(page_content=text or "", metadata=meta or {}))

            if len(ids) < GET_META_BATCH_SIZE:
                break
            offset += len(ids)

        if not all_docs:
            self._index = None
            self._documents = []
            self._doc_count = 0
            return

        tokenized = [_tokenize(d.page_content) for d in all_docs]
        self._index = BM25Okapi(tokenized)
        self._documents = all_docs
        self._doc_count = len(all_docs)
        logger.debug("BM25 index built with %d documents", self._doc_count)

    def search(
        self,
        query: str,
        k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Return the top-*k* BM25-scored documents, optionally filtered."""
        with self._lock:
            index = self._index
            documents = self._documents

        if index is None or not documents:
            return []

        tokens = _tokenize(query)
        if not tokens:
            return []

        scores = index.get_scores(tokens)

        scored: list[tuple[float, int, Document]] = []
        for i, (doc, score) in enumerate(zip(documents, scores, strict=False)):
            if metadata_filter:
                if not all(doc.metadata.get(k_) == v for k_, v in metadata_filter.items()):
                    continue
            scored.append((score, i, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, _, doc in scored[:k]]


# Module-level singleton so the BM25 index is shared across retrievers.
_bm25_index = BM25Index()


def reset_bm25_index() -> None:
    """Reset the shared BM25 index (e.g. for tests). Next retrieval will rebuild."""
    global _bm25_index
    _bm25_index = BM25Index()


def reciprocal_rank_fusion(
    result_lists: list[list[Document]],
    weights: list[float] | None = None,
    rrf_k: int = RRF_K,
    max_results: int = 20,
) -> list[Document]:
    """Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score for document *d*:

        score(d) = sum_i( weight_i / (rrf_k + rank_i(d)) )

    Higher *rrf_k* dampens the influence of top ranks, creating a smoother
    blend across lists.
    """
    if not result_lists:
        return []

    if weights is None:
        weights = [1.0] * len(result_lists)

    doc_scores: dict[str, tuple[float, Document]] = {}

    for lst_idx, doc_list in enumerate(result_lists):
        w = weights[lst_idx] if lst_idx < len(weights) else 1.0
        for rank, doc in enumerate(doc_list):
            key = f"{doc.metadata.get('doc_id', '')}\x00{doc.metadata.get('chunk_index', 0)}"
            current_score = doc_scores.get(key, (0.0, doc))[0]
            rrf_score = w / (rrf_k + rank + 1)
            doc_scores[key] = (current_score + rrf_score, doc)

    sorted_docs = sorted(doc_scores.values(), key=lambda x: x[0], reverse=True)
    return [doc for _, doc in sorted_docs[:max_results]]


def ensure_source_diversity(
    docs: list[Document],
    relevant_sources: dict[str, float],
    k: int,
    min_per_source: int = CROSS_SOURCE_MIN_PER_SOURCE,
) -> list[Document]:
    """Re-rank *docs* so that each relevant source has at least
    *min_per_source* representatives in the top-*k*, if available.

    Documents from under-represented sources are promoted from lower
    positions, displacing the lowest-ranked documents from
    over-represented sources. Summary documents (doc_type
    topic_summary or document_summary) are never displaced to satisfy
    source diversity.
    """
    if not docs or not relevant_sources:
        return docs[:k]

    _SUMMARY_DOC_TYPES = ("topic_summary", "document_summary")
    target_sources = {s for s, score in relevant_sources.items() if score > 0.2}
    if len(target_sources) <= 1:
        return docs[:k]

    top = list(docs[:k])
    remaining = list(docs[k:])

    source_counts: dict[str, int] = {}
    for doc in top:
        src = doc.metadata.get("source", "")
        source_counts[src] = source_counts.get(src, 0) + 1

    for src in target_sources:
        deficit = min_per_source - source_counts.get(src, 0)
        if deficit <= 0:
            continue

        promotions: list[Document] = []
        new_remaining: list[Document] = []
        for doc in remaining:
            if doc.metadata.get("source") == src and len(promotions) < deficit:
                promotions.append(doc)
            else:
                new_remaining.append(doc)
        remaining = new_remaining

        for promo in promotions:
            displaced = False
            # Prefer displacing an over-represented non-summary doc (scan low rank first)
            for i in range(len(top) - 1, -1, -1):
                src_i = top[i].metadata.get("source", "")
                if source_counts.get(src_i, 0) > min_per_source and top[
                    i
                ].metadata.get("doc_type") not in _SUMMARY_DOC_TYPES:
                    source_counts[src_i] -= 1
                    top.pop(i)
                    displaced = True
                    break
            # If no over-represented non-summary: make room by displacing the
            # lowest-ranked non-summary so deficit positions are still filled.
            if not displaced and len(top) >= k:
                for i in range(len(top) - 1, -1, -1):
                    if top[i].metadata.get("doc_type") not in _SUMMARY_DOC_TYPES:
                        popped_doc = top.pop(i)
                        popped_src = popped_doc.metadata.get("source", "")
                        source_counts[popped_src] = max(
                            0, source_counts.get(popped_src, 0) - 1
                        )
                        displaced = True
                        break
            if displaced:
                top.append(promo)
                source_counts[src] = source_counts.get(src, 0) + 1

    return top[:k]


class HybridRetriever(BaseRetriever):
    """Retriever that fuses semantic and BM25 keyword search, with
    cross-source diversification and LCD-aware query expansion.

    For every query:
      1. Expand the query into source-targeted variants.
      2. Run semantic search for each variant.
      3. Run BM25 keyword search for each variant.
      4. Fuse all result lists via Reciprocal Rank Fusion (RRF).
      5. Ensure source diversity in the final top-k.

    LCD-specific queries additionally trigger the original LCD query
    expansion (contractor/coverage-determination terms) so that MCD
    content gets extra retrieval weight.
    """

    model_config = {"arbitrary_types_allowed": True}

    store: Any
    k: int = 8
    lcd_k: int = LCD_RETRIEVAL_K
    metadata_filter: dict | None = None
    semantic_weight: float = HYBRID_SEMANTIC_WEIGHT
    keyword_weight: float = HYBRID_KEYWORD_WEIGHT

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        collection = get_raw_collection(self.store)
        _bm25_index.ensure_built(collection)

        effective_k = self.lcd_k if is_lcd_query(query) else self.k
        fetch_k = max(effective_k * 2, 20)

        variants = expand_cross_source_query(query)

        if is_lcd_query(query):
            lcd_variants = expand_lcd_query(query)
            for lv in lcd_variants[1:]:
                if lv not in variants:
                    variants.append(lv)

        variants = variants[:MAX_QUERY_VARIANTS]

        semantic_lists: list[list[Document]] = []
        keyword_lists: list[list[Document]] = []

        for variant in variants:
            search_kwargs: dict[str, Any] = {"k": fetch_k}
            if self.metadata_filter is not None:
                search_kwargs["filter"] = self.metadata_filter
            semantic_lists.append(self.store.similarity_search(variant, **search_kwargs))
            keyword_lists.append(
                _bm25_index.search(variant, k=fetch_k, metadata_filter=self.metadata_filter)
            )

        if is_lcd_query(query):
            mcd_filter = {"source": "mcd"}
            if self.metadata_filter is not None:
                mcd_filter = {**self.metadata_filter, "source": "mcd"}

            if self.metadata_filter is None or self.metadata_filter.get("source") in (
                None,
                "mcd",
            ):
                semantic_lists.append(
                    self.store.similarity_search(query, k=fetch_k, filter=mcd_filter)
                )
                keyword_lists.append(
                    _bm25_index.search(query, k=fetch_k, metadata_filter=mcd_filter)
                )

        all_lists = semantic_lists + keyword_lists
        n_semantic = len(semantic_lists)
        weights = [self.semantic_weight] * n_semantic + [self.keyword_weight] * len(keyword_lists)

        fused = reciprocal_rank_fusion(all_lists, weights=weights, max_results=fetch_k)

        fused = apply_topic_summary_boost(self.store, fused, query, fetch_k)

        relevance = detect_source_relevance(query)
        diversified = ensure_source_diversity(fused, relevance, effective_k)

        return diversified


def get_hybrid_retriever(
    k: int = 8,
    metadata_filter: dict | None = None,
    embeddings: Any = None,
    store: Any = None,
) -> HybridRetriever:
    """Convenience constructor that wires up embeddings and Chroma store.

    Raises ImportError if rank-bm25 is not installed, so callers (e.g.
    get_retriever) can catch it and fall back to a non-hybrid retriever.

    If embeddings and store are provided, they will be reused instead of
    creating new instances, avoiding redundant model loading.
    """
    if not _HAS_BM25:
        raise ImportError("rank-bm25 is required for hybrid retrieval")

    if embeddings is None or store is None:
        from medicare_rag.index import get_embeddings, get_or_create_chroma

        if embeddings is None:
            embeddings = get_embeddings()
        if store is None:
            store = get_or_create_chroma(embeddings)

    return HybridRetriever(
        store=store,
        k=k,
        lcd_k=max(k, LCD_RETRIEVAL_K),
        metadata_filter=metadata_filter,
    )
