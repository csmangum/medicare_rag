"""ChromaDB vector store (Phase 3)."""
import hashlib
import logging

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from medicare_rag.config import CHROMA_DIR, COLLECTION_NAME

logger = logging.getLogger(__name__)

# Chroma allows str, int, float, bool in metadata
def _sanitize_metadata(meta: dict) -> dict:
    out = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def _chunk_id(doc: Document) -> str:
    doc_id = doc.metadata.get("doc_id", "unknown")
    if "chunk_index" in doc.metadata:
        return f"{doc_id}_{doc.metadata['chunk_index']}"
    return doc_id


def _content_hash(doc: Document) -> str:
    doc_id = doc.metadata.get("doc_id", "unknown")
    chunk_index = doc.metadata.get("chunk_index", 0)
    payload = f"{doc.page_content}{doc_id}{chunk_index}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_or_create_chroma(embeddings: Embeddings):
    """Return a LangChain Chroma instance (persist_directory, collection_name, embedding_function)."""
    from langchain_chroma import Chroma

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


def upsert_documents(
    store,
    documents: list[Document],
    embeddings: Embeddings,
) -> tuple[int, int]:
    """Upsert documents into the Chroma store. Only embed and upsert new or changed chunks (by content_hash).
    Returns (new_or_updated_count, skipped_count).
    """
    if not documents:
        return 0, 0

    collection = store._collection
    # Existing ids -> content_hash
    existing = collection.get(include=["metadatas"])
    id_to_hash = {}
    if existing and existing.get("ids"):
        for i, id_ in enumerate(existing["ids"]):
            meta = (existing.get("metadatas") or [{}])[i] or {}
            id_to_hash[id_] = meta.get("content_hash", "")

    to_upsert: list[Document] = []
    for doc in documents:
        cid = _chunk_id(doc)
        new_hash = _content_hash(doc)
        if id_to_hash.get(cid) == new_hash:
            continue
        to_upsert.append(doc)

    skipped = len(documents) - len(to_upsert)
    if not to_upsert:
        return 0, skipped

    texts = [d.page_content for d in to_upsert]
    vectors = embeddings.embed_documents(texts)

    ids = [_chunk_id(d) for d in to_upsert]
    metadatas = []
    for d in to_upsert:
        meta = dict(d.metadata)
        meta["content_hash"] = _content_hash(d)
        metadatas.append(_sanitize_metadata(meta))

    collection.upsert(
        ids=ids,
        embeddings=vectors,
        metadatas=metadatas,
        documents=texts,
    )
    return len(to_upsert), skipped
