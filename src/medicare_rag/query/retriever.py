"""LCD-aware VectorStoreRetriever (Phase 4).

Provides a retriever that detects LCD/coverage-determination queries and
applies query expansion plus source-filtered multi-query retrieval to
improve hit rates on MCD policy content.

Summary documents (``doc_type`` = ``document_summary`` or ``topic_summary``)
are boosted in retrieval results to provide stable "anchor" chunks that
match consistently regardless of query phrasing.
"""
import logging
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from medicare_rag.config import LCD_RETRIEVAL_K
from medicare_rag.index import get_embeddings, get_or_create_chroma
from medicare_rag.index.store import get_raw_collection

logger = logging.getLogger(__name__)

_LCD_QUERY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\blcds?\b",
        r"\blocal coverage determination\b",
        r"\bcoverage determination\b",
        r"\bncd\b",
        r"\bnational coverage determination\b",
        r"\bmcd\b",
        r"\bcontractor\b",
        r"\bjurisdiction\b",
        # MAC contractor names
        r"\bnovitas\b",
        r"\bfirst coast\b",
        r"\bcgs\b",
        r"\bngs\b",
        r"\bwps\b",
        r"\bpalmetto\b",
        r"\bnoridian\b",
        # Jurisdiction codes
        r"\b[jJ][a-l]\b",
        # Coverage + specific therapy patterns common in LCD queries
        r"\bcover(?:ed)?\b.{0,40}\b(?:wound|hyperbaric|oxygen therapy|infusion|"
        r"imaging|MRI|CT scan|ultrasound|physical therapy|"
        r"cardiac rehab|chiropractic|acupuncture)\b",
        r"\bcoverage\b.{0,30}\b(?:wound|hyperbaric|oxygen|infusion|"
        r"imaging|MRI|CT|physical therapy|cardiac|"
        r"chiropractic|acupuncture|prosthetic|orthotic)\b",
        # Reverse: therapy term then coverage verb
        r"\b(?:wound|hyperbaric|oxygen therapy|infusion|"
        r"imaging|MRI|CT scan|physical therapy|cardiac rehab)"
        r"\b.{0,40}\bcover(?:ed)?\b",
    ]
]

_LCD_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), expansion)
    for p, expansion in [
        (r"\bcardiac\s*rehab", "cardiac rehabilitation program coverage criteria"),
        (r"\bhyperbaric\s*oxygen", "hyperbaric oxygen therapy wound healing coverage indications"),
        (r"\bphysical therapy", "outpatient physical therapy rehabilitation coverage"),
        (r"\b(?:wound\s*care|wound\s*vac)", "wound care negative pressure therapy coverage"),
        (r"\b(?:imaging|MRI|CT\s*scan)", "advanced diagnostic imaging coverage medical necessity"),
    ]
]


def is_lcd_query(query: str) -> bool:
    """Return True if the query appears to be about LCD/coverage determinations."""
    return any(p.search(query) for p in _LCD_QUERY_PATTERNS)


_STRIP_LCD_NOISE = re.compile(
    r"\b(?:lcd|lcds|ncd|mcd|local coverage determination|"
    r"national coverage determination|coverage determination|"
    r"novitas|first coast|cgs|ngs|wps|palmetto|noridian|"
    r"contractor|jurisdiction|"
    r"[jJ][a-lA-L])\b",
    re.IGNORECASE,
)
_STRIP_FILLER = re.compile(
    r"\b(?:does|have|has|an|the|for|is|are|what|which|apply to)\b",
    re.IGNORECASE,
)


def _strip_to_medical_concept(query: str) -> str:
    """Remove LCD jargon, contractor names, and filler words to isolate
    the medical concept from a coverage-determination query."""
    cleaned = _STRIP_LCD_NOISE.sub("", query)
    cleaned = _STRIP_FILLER.sub("", cleaned)
    cleaned = re.sub(r"[()]+", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ?.,;:")
    return cleaned


def expand_lcd_query(query: str) -> list[str]:
    """Return a list of expanded/reformulated queries for LCD retrieval.

    Produces up to three variants:
      1. The original query (unchanged).
      2. Original + topic-specific expansion terms.
      3. A stripped medical-concept query (contractor/LCD terms removed)
         so the embedding focuses on the clinical topic.
    """
    queries = [query]

    topic_expansions = [
        exp for pat, exp in _LCD_TOPIC_PATTERNS if pat.search(query)
    ]

    if topic_expansions:
        queries.append(f"{query} {' '.join(topic_expansions)}")
    else:
        queries.append(
            f"{query} Local Coverage Determination LCD policy"
            " coverage criteria"
        )

    concept = _strip_to_medical_concept(query)
    if concept and concept.lower() != query.lower():
        queries.append(concept)

    return queries


def detect_query_topics(query: str) -> list[str]:
    """Return the list of topic cluster names relevant to the query."""
    from medicare_rag.ingest.cluster import assign_topics

    return assign_topics(Document(page_content=query, metadata={}))


def boost_summaries(
    docs: list[Document],
    query_topics: list[str],
    max_k: int,
) -> list[Document]:
    """Re-rank *docs* so that topic/document summaries matching the query
    topics appear near the top of the result list.

    Summary documents act as stable anchors: they consolidate fragmented
    content and match consistently regardless of how the question is phrased.
    """
    if not query_topics or not docs:
        return docs[:max_k]

    topic_set = set(query_topics)
    boosted: list[Document] = []
    rest: list[Document] = []

    for doc in docs:
        doc_type = doc.metadata.get("doc_type", "")
        topic_cluster = doc.metadata.get("topic_cluster", "")
        topic_clusters = doc.metadata.get("topic_clusters", "")

        is_relevant_summary = False
        if doc_type in ("topic_summary", "document_summary"):
            if topic_cluster and topic_cluster in topic_set:
                is_relevant_summary = True
            elif topic_clusters:
                doc_topics = set(topic_clusters.split(","))
                if doc_topics & topic_set:
                    is_relevant_summary = True

        if is_relevant_summary:
            boosted.append(doc)
        else:
            rest.append(doc)

    return (boosted + rest)[:max_k]


def inject_topic_summaries(
    store: Any,
    docs: list[Document],
    query_topics: list[str],
    max_k: int,
) -> list[Document]:
    """Prepend topic summary docs for detected topics when not already in docs.

    Ensures stable anchor docs are always present in the candidate set before
    boosting, fixing the fragmented content consistency gap when topic summaries
    don't rank in top-k by similarity.
    """
    if not query_topics:
        return docs[:max_k]

    ids = [f"topic_{t}" for t in query_topics]
    collection = get_raw_collection(store)
    result = collection.get(ids=ids, include=["documents", "metadatas"])

    returned_ids = result.get("ids") or []
    texts = result.get("documents") or []
    metas = result.get("metadatas") or []

    injected: list[Document] = []
    for i, _cid in enumerate(returned_ids):
        text = texts[i] if i < len(texts) else ""
        meta = (metas[i] if i < len(metas) else None) or {}
        injected.append(Document(page_content=text or "", metadata=dict(meta)))

    existing_ids = {d.metadata.get("doc_id", "") for d in docs}
    new_injected = [d for d in injected if d.metadata.get("doc_id", "") not in existing_ids]
    if new_injected:
        logger.debug(
            "Injected %d topic summaries for query topics: %s",
            len(new_injected),
            ", ".join(query_topics),
        )
    combined = new_injected + docs
    return combined[:max_k]


def apply_topic_summary_boost(
    store: Any,
    docs: list[Document],
    query: str,
    max_k: int,
) -> list[Document]:
    """Run topic detection, inject topic summaries if needed, boost them,
    return up to max_k docs."""
    query_topics = detect_query_topics(query)
    if query_topics:
        docs = inject_topic_summaries(store, docs, query_topics, max_k)
        docs = boost_summaries(docs, query_topics, max_k)
    return docs[:max_k]


def _deduplicate_docs(
    doc_lists: list[list[Document]], max_k: int,
) -> list[Document]:
    """Merge doc lists via round-robin interleaving, deduplicating by
    doc_id+chunk_index.  This ensures each query variant contributes
    docs near the top of the final list rather than one variant
    dominating all slots."""
    seen: set[str] = set()
    merged: list[Document] = []
    max_len = max((len(dl) for dl in doc_lists), default=0)
    for pos in range(max_len):
        for dl in doc_lists:
            if pos >= len(dl):
                continue
            doc = dl[pos]
            key = (
                f"{doc.metadata.get('doc_id', '')}"
                f"\x00{doc.metadata.get('chunk_index', 0)}"
            )
            if key not in seen:
                seen.add(key)
                merged.append(doc)
                if len(merged) >= max_k:
                    return merged
    return merged


class LCDAwareRetriever(BaseRetriever):
    """Retriever that boosts LCD/MCD retrieval via query expansion and source-filtered search.

    For non-LCD queries, delegates to standard similarity search with ``k`` results.
    For LCD queries:
      1. Computes a per-variant ``k`` as ``max(4, lcd_k // 3)``.
      2. Runs the original query restricted to MCD source with this per-variant ``k``.
      3. Runs expanded/reformulated MCD queries, each with the same per-variant ``k``.
      4. Runs the original query with the general metadata filter (if any) using the
         per-variant ``k``.
      5. Merges and deduplicates results from all variants, returning up to ``lcd_k``
         documents.
    """

    model_config = {"arbitrary_types_allowed": True}

    store: Any
    k: int = 8
    lcd_k: int = LCD_RETRIEVAL_K
    metadata_filter: dict | None = None

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        if is_lcd_query(query):
            return self._lcd_retrieve(query)
        search_kwargs: dict = {"k": self.k}
        if self.metadata_filter is not None:
            search_kwargs["filter"] = self.metadata_filter
        docs = self.store.similarity_search(query, **search_kwargs)
        docs = apply_topic_summary_boost(self.store, docs, query, self.k)
        return docs

    def _lcd_retrieve(self, query: str) -> list[Document]:
        # If metadata_filter explicitly specifies a non-MCD source, skip LCD-aware
        # retrieval to honor the user's source filter
        if (
            self.metadata_filter is not None
            and self.metadata_filter.get("source") not in (None, "mcd")
        ):
            search_kwargs = {"k": self.k, "filter": self.metadata_filter}
            return self.store.similarity_search(query, **search_kwargs)

        mcd_filter = {"source": "mcd"}
        if self.metadata_filter is not None:
            mcd_filter = {**self.metadata_filter, "source": "mcd"}

        per_variant = max(4, self.lcd_k // 3)

        mcd_docs = self.store.similarity_search(
            query, k=per_variant, filter=mcd_filter
        )

        expanded_queries = expand_lcd_query(query)
        variant_results: list[list[Document]] = []
        for eq in expanded_queries[1:]:
            variant_results.append(
                self.store.similarity_search(
                    eq, k=per_variant, filter=mcd_filter,
                )
            )

        base_kwargs: dict = {"k": per_variant}
        if self.metadata_filter is not None:
            base_kwargs["filter"] = self.metadata_filter
        base_docs = self.store.similarity_search(query, **base_kwargs)

        doc_lists = [mcd_docs] + variant_results + [base_docs]
        merged = _deduplicate_docs(doc_lists, max_k=self.lcd_k)
        merged = apply_topic_summary_boost(self.store, merged, query, self.lcd_k)
        return merged


def get_retriever(
    k: int = 8,
    metadata_filter: dict | None = None,
    embeddings: Any = None,
    store: Any = None,
) -> BaseRetriever:
    """Return a hybrid retriever combining semantic and keyword search.

    The hybrid retriever handles LCD-aware expansion, cross-source query
    expansion, BM25 keyword search, and source diversification.  Falls
    back to the simpler :class:`LCDAwareRetriever` when the ``rank-bm25``
    dependency is unavailable.

    Uses the same embeddings and persist directory as the index. Optional
    metadata_filter is passed to Chroma's where clause (e.g. {"source": "iom"},
    {"manual": "100-02"}, {"jurisdiction": "JL"}).

    If embeddings and store are provided, they will be reused instead of
    creating new instances, avoiding redundant model loading.
    """
    try:
        from medicare_rag.query.hybrid import get_hybrid_retriever

        return get_hybrid_retriever(
            k=k, metadata_filter=metadata_filter, embeddings=embeddings, store=store
        )
    except ImportError:
        pass

    if embeddings is None:
        embeddings = get_embeddings()
    if store is None:
        store = get_or_create_chroma(embeddings)
    return LCDAwareRetriever(
        store=store,
        k=k,
        lcd_k=max(k, LCD_RETRIEVAL_K),
        metadata_filter=metadata_filter,
    )
