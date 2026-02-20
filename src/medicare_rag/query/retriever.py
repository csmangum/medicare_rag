"""LCD-aware VectorStoreRetriever (Phase 4).

Provides a retriever that detects LCD/coverage-determination queries and
applies query expansion plus source-filtered multi-query retrieval to
improve hit rates on MCD policy content.
"""
import re
from typing import Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from medicare_rag.config import LCD_RETRIEVAL_K
from medicare_rag.index import get_embeddings, get_or_create_chroma

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
                f"_{doc.metadata.get('chunk_index', 0)}"
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
        return self.store.similarity_search(query, **search_kwargs)

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
        return _deduplicate_docs(doc_lists, max_k=self.lcd_k)


def get_retriever(
    k: int = 8,
    metadata_filter: dict | None = None,
) -> BaseRetriever:
    """Return a hybrid retriever combining semantic and keyword search.

    The hybrid retriever handles LCD-aware expansion, cross-source query
    expansion, BM25 keyword search, and source diversification.  Falls
    back to the simpler :class:`LCDAwareRetriever` when the ``rank-bm25``
    dependency is unavailable.

    Uses the same embeddings and persist directory as the index. Optional
    metadata_filter is passed to Chroma's where clause (e.g. {"source": "iom"},
    {"manual": "100-02"}, {"jurisdiction": "JL"}).
    """
    try:
        from medicare_rag.query.hybrid import get_hybrid_retriever

        return get_hybrid_retriever(k=k, metadata_filter=metadata_filter)
    except ImportError:
        pass

    embeddings = get_embeddings()
    store = get_or_create_chroma(embeddings)
    return LCDAwareRetriever(
        store=store,
        k=k,
        lcd_k=max(k, LCD_RETRIEVAL_K),
        metadata_filter=metadata_filter,
    )
