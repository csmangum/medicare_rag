"""Tests for embedding and vector store (Phase 3)."""
from pathlib import Path
from unittest.mock import patch

import pytest

from langchain_core.documents import Document

from medicare_rag.index.embed import get_embeddings
from medicare_rag.index.store import (
    _chunk_id,
    _content_hash,
    _sanitize_metadata,
    get_or_create_chroma,
    upsert_documents,
)

# ChromaDB uses pydantic v1 and can fail to import (e.g. on Python 3.14+)
try:
    import chromadb  # noqa: F401
    _chroma_available = True
except Exception:
    _chroma_available = False


def test_get_embeddings_returns_embeddings() -> None:
    emb = get_embeddings()
    assert emb is not None


def test_embed_documents_shape_and_dimension() -> None:
    """embed_documents returns list of vectors; each vector is 384 dims for all-MiniLM-L6-v2."""
    emb = get_embeddings()
    texts = ["First document.", "Second document."]
    vectors = emb.embed_documents(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert len(vectors[1]) == 384
    assert all(isinstance(x, float) for x in vectors[0])


def test_sanitize_metadata_omits_none() -> None:
    assert _sanitize_metadata({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}


def test_sanitize_metadata_coerces_non_scalar_to_str() -> None:
    out = _sanitize_metadata({"k": [1, 2]})
    assert out["k"] == "[1, 2]"


def test_chunk_id_with_chunk_index() -> None:
    doc = Document(page_content="x", metadata={"doc_id": "iom_1", "chunk_index": 2})
    assert _chunk_id(doc) == "iom_1_2"


def test_chunk_id_without_chunk_index() -> None:
    doc = Document(page_content="x", metadata={"doc_id": "codes_A1001"})
    assert _chunk_id(doc) == "codes_A1001"


def test_content_hash_deterministic() -> None:
    doc = Document(page_content="hello", metadata={"doc_id": "d1", "chunk_index": 0})
    assert _content_hash(doc) == _content_hash(doc)
    doc2 = Document(page_content="hello", metadata={"doc_id": "d1", "chunk_index": 0})
    assert _content_hash(doc) == _content_hash(doc2)


def test_content_hash_changes_with_content() -> None:
    doc1 = Document(page_content="a", metadata={"doc_id": "d1", "chunk_index": 0})
    doc2 = Document(page_content="b", metadata={"doc_id": "d1", "chunk_index": 0})
    assert _content_hash(doc1) != _content_hash(doc2)


@pytest.fixture
def chroma_dir(tmp_path: Path):
    return tmp_path / "chroma"


@pytest.mark.skipif(not _chroma_available, reason="ChromaDB not available (e.g. pydantic v1 on Python 3.14+)")
def test_get_or_create_chroma_and_upsert(chroma_dir: Path) -> None:
    with patch("medicare_rag.index.store.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.index.store.COLLECTION_NAME", "test_medicare_rag"
    ):
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        docs = [
            Document(
                page_content="Medicare Part B covers outpatient care.",
                metadata={"doc_id": "iom_100-02_ch6", "chunk_index": 0, "source": "iom"},
            ),
            Document(
                page_content="LCD L12345 describes coverage for cardiac rehab.",
                metadata={"doc_id": "mcd_L12345", "chunk_index": 0, "source": "mcd"},
            ),
        ]
        n_upserted, n_skipped = upsert_documents(store, docs, embeddings)
        assert n_upserted == 2
        assert n_skipped == 0

        # Query by similarity
        results = store.similarity_search("cardiac rehab", k=1)
        assert len(results) >= 1
        assert "cardiac" in results[0].page_content or "LCD" in results[0].page_content
        assert results[0].metadata.get("source") in ("iom", "mcd")


@pytest.mark.skipif(not _chroma_available, reason="ChromaDB not available (e.g. pydantic v1 on Python 3.14+)")
def test_upsert_documents_incremental_skips_unchanged(chroma_dir: Path) -> None:
    with patch("medicare_rag.index.store.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.index.store.COLLECTION_NAME", "test_medicare_rag_incr"
    ):
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        docs = [
            Document(
                page_content="Content A.",
                metadata={"doc_id": "doc1", "chunk_index": 0},
            ),
            Document(
                page_content="Content B.",
                metadata={"doc_id": "doc2", "chunk_index": 0},
            ),
        ]
        n1, skip1 = upsert_documents(store, docs, embeddings)
        assert n1 == 2
        assert skip1 == 0

        # Same docs again -> all skipped
        n2, skip2 = upsert_documents(store, docs, embeddings)
        assert n2 == 0
        assert skip2 == 2


@pytest.mark.skipif(not _chroma_available, reason="ChromaDB not available (e.g. pydantic v1 on Python 3.14+)")
def test_upsert_documents_incremental_updates_changed(chroma_dir: Path) -> None:
    with patch("medicare_rag.index.store.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.index.store.COLLECTION_NAME", "test_medicare_rag_change"
    ):
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        docs = [
            Document(
                page_content="Original text.",
                metadata={"doc_id": "d1", "chunk_index": 0},
            ),
            Document(
                page_content="Unchanged text.",
                metadata={"doc_id": "d2", "chunk_index": 0},
            ),
        ]
        upsert_documents(store, docs, embeddings)

        # Change one document
        docs[0] = Document(
            page_content="Updated text.",
            metadata={"doc_id": "d1", "chunk_index": 0},
        )
        docs[1] = Document(
            page_content="Unchanged text.",
            metadata={"doc_id": "d2", "chunk_index": 0},
        )
        n_upserted, n_skipped = upsert_documents(store, docs, embeddings)
        assert n_upserted == 1
        assert n_skipped == 1

        results = store.similarity_search("Updated text", k=1)
        assert len(results) >= 1
        assert "Updated" in results[0].page_content


def test_upsert_documents_empty_list() -> None:
    class MockCollection:
        def get(self, include=None):
            return {"ids": [], "metadatas": []}

    class MockStore:
        _collection = MockCollection()

    emb = get_embeddings()
    n, skip = upsert_documents(MockStore(), [], emb)
    assert n == 0
    assert skip == 0
