"""LCD-aware VectorStoreRetriever (Phase 4).

Provides a retriever that detects LCD/coverage-determination queries and
applies query expansion plus source-filtered multi-query retrieval to
improve hit rates on MCD policy content.
"""
import re
from typing import TYPE_CHECKING, Any

from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from medicare_rag.config import LCD_RETRIEVAL_K
from medicare_rag.index import get_embeddings, get_or_create_chroma

if TYPE_CHECKING:
    from langchain_chroma import Chroma

_LCD_QUERY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\blcd\b",
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
        r"\bcgs\b",
        # Jurisdiction codes
        r"\b[jJ][a-lA-L]\b",
    ]
]

_LCD_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), expansion)
    for p, expansion in [
        (r"\bcardiac\s*rehab", "cardiac rehabilitation program coverage criteria"),
        (r"\bhyperbaric\s*oxygen", "hyperbaric oxygen therapy wound healing coverage indications"),
        (r"\bphysical therapy", "outpatient physical therapy rehabilitation coverage"),
        (r"\bwound\s*care|wound\s*vac", "wound care negative pressure therapy coverage"),
        (r"\bimaging|MRI|CT\s*scan", "advanced diagnostic imaging coverage medical necessity"),
    ]
]


def is_lcd_query(query: str) -> bool:
    """Return True if the query appears to be about LCD/coverage determinations."""
    return any(p.search(query) for p in _LCD_QUERY_PATTERNS)


def expand_lcd_query(query: str) -> list[str]:
    """Return a list of expanded/reformulated queries for LCD retrieval.

    Always returns the original query plus one or more reformulations
    designed to better match LCD policy text in the vector store.
    """
    queries = [query]

    topic_expansions = [
        exp for pat, exp in _LCD_TOPIC_PATTERNS if pat.search(query)
    ]

    if topic_expansions:
        queries.append(f"{query} {' '.join(topic_expansions)}")
    else:
        queries.append(
            f"{query} Local Coverage Determination LCD policy coverage criteria"
        )

    return queries


def _deduplicate_docs(doc_lists: list[list[Document]], max_k: int) -> list[Document]:
    """Merge multiple document lists, preserving order and removing duplicates by doc_id+chunk_index."""
    seen: set[str] = set()
    merged: list[Document] = []
    for docs in doc_lists:
        for doc in docs:
            key = f"{doc.metadata.get('doc_id', '')}_{doc.metadata.get('chunk_index', 0)}"
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
      1. Runs the original query with a higher k (``lcd_k``).
      2. Runs a source-filtered query (source=mcd) to guarantee MCD docs appear.
      3. Runs expanded/reformulated queries to capture variant phrasing.
      4. Merges and deduplicates, returning up to ``lcd_k`` results.
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
        base_kwargs: dict = {"k": self.lcd_k}
        if self.metadata_filter is not None:
            base_kwargs["filter"] = self.metadata_filter

        base_docs = self.store.similarity_search(query, **base_kwargs)

        mcd_filter = {"source": "mcd"}
        if self.metadata_filter is not None:
            mcd_filter = {**self.metadata_filter, "source": "mcd"}
        mcd_docs = self.store.similarity_search(
            query, k=self.lcd_k, filter=mcd_filter
        )

        expanded_queries = expand_lcd_query(query)
        expanded_docs: list[Document] = []
        for eq in expanded_queries[1:]:
            expanded_docs.extend(
                self.store.similarity_search(eq, **base_kwargs)
            )

        return _deduplicate_docs(
            [base_docs, mcd_docs, expanded_docs], max_k=self.lcd_k
        )


def get_retriever(
    k: int = 8,
    metadata_filter: dict | None = None,
) -> BaseRetriever:
    """Return an LCD-aware retriever over the Chroma store.

    Uses the same embeddings and persist directory as the index. Optional
    metadata_filter is passed to Chroma's where clause (e.g. {"source": "iom"},
    {"manual": "100-02"}, {"jurisdiction": "JL"}).
    """
    embeddings = get_embeddings()
    store = get_or_create_chroma(embeddings)
    return LCDAwareRetriever(
        store=store,
        k=k,
        lcd_k=max(k, LCD_RETRIEVAL_K),
        metadata_filter=metadata_filter,
    )
