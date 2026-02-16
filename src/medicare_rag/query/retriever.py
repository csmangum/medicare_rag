"""VectorStoreRetriever (Phase 4)."""
from typing import TYPE_CHECKING

from medicare_rag.index import get_embeddings, get_or_create_chroma

if TYPE_CHECKING:
    from langchain_core.retrievers import BaseRetriever


def get_retriever(
    k: int = 8,
    metadata_filter: dict | None = None,
) -> "BaseRetriever":
    """Return a LangChain retriever over the Chroma store.

    Uses the same embeddings and persist directory as the index. Optional
    metadata_filter is passed to Chroma's where clause (e.g. {"source": "iom"},
    {"manual": "100-02"}, {"jurisdiction": "JL"}).
    """
    embeddings = get_embeddings()
    store = get_or_create_chroma(embeddings)
    search_kwargs: dict = {"k": k}
    if metadata_filter is not None:
        search_kwargs["filter"] = metadata_filter
    return store.as_retriever(search_kwargs=search_kwargs)
