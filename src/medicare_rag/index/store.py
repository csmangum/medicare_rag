"""ChromaDB vector store operations (Phase 3).

Provides incremental upsert by content hash so that unchanged chunks are
not re-embedded on repeated ingestion runs.
"""
import hashlib
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

if TYPE_CHECKING:
    from langchain_chroma import Chroma

from medicare_rag.config import (
    CHROMA_DIR,
    CHROMA_UPSERT_BATCH_SIZE,
    COLLECTION_NAME,
    GET_META_BATCH_SIZE,
)


def get_raw_collection(store: "Chroma"):
    """Access the underlying ChromaDB collection from a LangChain Chroma wrapper.
    Raises RuntimeError if the private API has changed.
    """
    coll = getattr(store, "_collection", None)
    if coll is None:
        raise RuntimeError(
            "langchain-chroma API changed: _collection not found. "
            f"Pin langchain-chroma or update {__name__}."
        )
    return coll


def _sanitize_metadata(meta: dict) -> dict:
    """Coerce metadata values to ChromaDB-compatible types (str/int/float/bool), dropping None."""
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
    """Stable identifier for a chunk: ``{doc_id}_{chunk_index}`` or plain ``{doc_id}`` for single-chunk docs."""
    doc_id = doc.metadata.get("doc_id", "unknown")
    if "chunk_index" in doc.metadata:
        return f"{doc_id}_{doc.metadata['chunk_index']}"
    return doc_id


def _content_hash(doc: Document) -> str:
    """SHA-256 of ``page_content + doc_id + chunk_index`` for change detection."""
    doc_id = doc.metadata.get("doc_id", "unknown")
    chunk_index = doc.metadata.get("chunk_index", 0)
    payload = f"{doc.page_content}\x00{doc_id}\x00{chunk_index}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_or_create_chroma(embeddings: Embeddings) -> "Chroma":
    """Return a LangChain Chroma instance (persist_directory, collection_name, embedding_function)."""
    from langchain_chroma import Chroma

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


def upsert_documents(
    store: "Chroma",
    documents: list[Document],
    embeddings: Embeddings,
) -> tuple[int, int]:
    """Upsert documents into the Chroma store. Only embed and upsert new or changed chunks (by content_hash).
    Returns (new_or_updated_count, skipped_count).
    """
    if not documents:
        return 0, 0

    # We use the LangChain Chroma wrapper's _collection for batched get(include=["metadatas"])
    # and upsert() to support incremental indexing by content_hash. Batched get avoids
    # SQLite "too many SQL variables" when the collection is large.
    collection = get_raw_collection(store)
    id_to_hash: dict[str, str] = {}
    offset = 0
    while True:
        batch = collection.get(
            include=["metadatas"],
            limit=GET_META_BATCH_SIZE,
            offset=offset,
        )
        ids_batch = batch.get("ids") or []
        metadatas_list = batch.get("metadatas") or []
        for i, id_ in enumerate(ids_batch):
            meta = (metadatas_list[i] if i < len(metadatas_list) else None) or {}
            id_to_hash[id_] = meta.get("content_hash", "")
        if len(ids_batch) < GET_META_BATCH_SIZE:
            break
        offset += len(ids_batch)

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

    for i in range(0, len(to_upsert), CHROMA_UPSERT_BATCH_SIZE):
        end = i + CHROMA_UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[i:end],
            embeddings=vectors[i:end],
            metadatas=metadatas[i:end],
            documents=texts[i:end],
        )
    return len(to_upsert), skipped
