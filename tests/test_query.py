"""Tests for retriever and query chain (Phase 4)."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from langchain_core.documents import Document

from medicare_rag.index import get_embeddings, get_or_create_chroma
from medicare_rag.index.store import upsert_documents

try:
    import chromadb  # noqa: F401
    _chroma_available = True
except Exception:
    _chroma_available = False


@pytest.fixture
def chroma_dir(tmp_path: Path) -> Path:
    return tmp_path / "chroma"


@pytest.mark.skipif(not _chroma_available, reason="ChromaDB not available")
def test_get_retriever_returns_k_docs_with_metadata(chroma_dir: Path) -> None:
    with patch("medicare_rag.config.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.config.COLLECTION_NAME", "test_medicare_rag_query"
    ), patch("medicare_rag.index.store.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.index.store.COLLECTION_NAME", "test_medicare_rag_query"
    ):
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        docs = [
            Document(
                page_content="Medicare Part B covers outpatient care.",
                metadata={"doc_id": "iom_100-02_ch6", "chunk_index": 0, "source": "iom"},
            ),
            Document(
                page_content="LCD L12345 describes cardiac rehab coverage.",
                metadata={"doc_id": "mcd_L12345", "chunk_index": 0, "source": "mcd"},
            ),
        ]
        upsert_documents(store, docs, embeddings)

        from medicare_rag.query.retriever import get_retriever

        retriever = get_retriever(k=2)
        results = retriever.invoke("cardiac rehab")
        assert len(results) == 2
        for d in results:
            assert "source" in d.metadata
            assert "doc_id" in d.metadata


@pytest.mark.skipif(not _chroma_available, reason="ChromaDB not available")
def test_get_retriever_metadata_filter(chroma_dir: Path) -> None:
    with patch("medicare_rag.config.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.config.COLLECTION_NAME", "test_medicare_rag_filter"
    ), patch("medicare_rag.index.store.CHROMA_DIR", chroma_dir), patch(
        "medicare_rag.index.store.COLLECTION_NAME", "test_medicare_rag_filter"
    ):
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        docs = [
            Document(
                page_content="IOM chapter content.",
                metadata={"doc_id": "iom_1", "chunk_index": 0, "source": "iom"},
            ),
            Document(
                page_content="MCD LCD content.",
                metadata={"doc_id": "mcd_1", "chunk_index": 0, "source": "mcd"},
            ),
        ]
        upsert_documents(store, docs, embeddings)

        from medicare_rag.query.retriever import get_retriever

        retriever = get_retriever(k=2, metadata_filter={"source": "iom"})
        results = retriever.invoke("chapter")
        assert len(results) <= 2
        for d in results:
            assert d.metadata.get("source") == "iom"


def test_build_rag_chain_returns_callable() -> None:
    from medicare_rag.query.chain import build_rag_chain

    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        Document(page_content="Context chunk.", metadata={"source": "iom", "doc_id": "1"}),
    ]
    class FakeResponse:
        content = "Test answer from LLM."

    with patch("medicare_rag.query.chain._create_llm", return_value=MagicMock()), patch(
        "medicare_rag.query.chain.get_retriever", return_value=mock_retriever
    ), patch("medicare_rag.query.chain._invoke_chain", return_value=FakeResponse()):
        invoke = build_rag_chain(retriever=mock_retriever)
        result = invoke({"question": "What is coverage?"})

    assert result["answer"] == "Test answer from LLM."
    assert len(result["source_documents"]) == 1
    assert result["source_documents"][0].page_content == "Context chunk."
    mock_retriever.invoke.assert_called_with("What is coverage?")


def test_run_rag_returns_answer_and_source_docs() -> None:
    from medicare_rag.query.chain import run_rag

    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        Document(page_content="Policy text.", metadata={"source": "mcd", "doc_id": "L99"}),
    ]
    class FakeResponse:
        content = "Cited answer."

    with patch("medicare_rag.query.chain._create_llm", return_value=MagicMock()), patch(
        "medicare_rag.query.chain.get_retriever", return_value=mock_retriever
    ), patch("medicare_rag.query.chain._invoke_chain", return_value=FakeResponse()):
        answer, source_docs = run_rag("What does the policy say?", retriever=mock_retriever)

    assert answer == "Cited answer."
    assert len(source_docs) == 1
    assert source_docs[0].metadata.get("source") == "mcd"


def test_run_eval_returns_metrics_for_one_question(tmp_path: Path) -> None:
    """Phase 5: retrieval eval path run_eval returns expected metrics structure."""
    import importlib.util
    import json

    eval_file = tmp_path / "eval_one.json"
    eval_file.write_text(
        json.dumps([
            {
                "id": "part_b",
                "query": "What does Medicare Part B cover?",
                "expected_keywords": ["Part B", "outpatient"],
                "expected_sources": ["iom"],
                "category": "policy_coverage",
                "difficulty": "easy",
            }
        ]),
        encoding="utf-8",
    )
    mock_retriever = MagicMock()
    mock_retriever.invoke.return_value = [
        Document(
            page_content="Medicare Part B covers outpatient medical services.",
            metadata={"doc_id": "iom_1", "chunk_index": 0, "source": "iom"},
        ),
    ]
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "validate_and_eval.py"
    spec = importlib.util.spec_from_file_location("validate_and_eval", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with patch.object(mod, "_load_retriever", return_value=mock_retriever):
        metrics = mod.run_eval(eval_file, k=5)

    assert metrics["n_questions"] == 1
    assert metrics["hit_rate"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["avg_precision_at_k"] > 0
    assert metrics["avg_ndcg_at_k"] > 0
    assert "latency" in metrics
    assert "by_category" in metrics
    assert "by_difficulty" in metrics
    assert len(metrics["results"]) == 1
    assert metrics["results"][0]["hit"] is True
    assert metrics["results"][0]["first_hit_rank"] == 1
