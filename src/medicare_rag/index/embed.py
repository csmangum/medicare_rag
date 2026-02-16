"""Local sentence-transformers embeddings (Phase 3)."""
from langchain_core.embeddings import Embeddings

from medicare_rag.config import EMBEDDING_MODEL


def get_embeddings() -> Embeddings:
    """Return a LangChain-compatible Embeddings instance using local sentence-transformers."""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
