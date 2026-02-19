"""Tests for retriever and query chain (Phase 4), including LCD-aware retrieval."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from medicare_rag.index import get_embeddings, get_or_create_chroma
from medicare_rag.index.store import upsert_documents
from medicare_rag.query.retriever import (
    LCDAwareRetriever,
    _deduplicate_docs,
    _strip_to_medical_concept,
    expand_lcd_query,
    is_lcd_query,
)

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


# ---------------------------------------------------------------------------
# LCD query detection tests
# ---------------------------------------------------------------------------

class TestIsLcdQuery:

    def test_explicit_lcd_term(self):
        assert is_lcd_query("What is the LCD for cardiac rehab?") is True

    def test_lcds_plural(self):
        assert is_lcd_query("What LCDs apply to outpatient physical therapy services?") is True

    def test_coverage_determination(self):
        assert is_lcd_query("local coverage determination criteria") is True

    def test_national_coverage(self):
        assert is_lcd_query("NCD coverage for imaging") is True

    def test_contractor_name_novitas(self):
        assert is_lcd_query("Does Novitas (JL) have an LCD for cardiac rehab?") is True

    def test_contractor_name_palmetto(self):
        assert is_lcd_query("Palmetto GBA policy on wound care") is True

    def test_jurisdiction_code(self):
        assert is_lcd_query("JL jurisdiction cardiac rehabilitation") is True

    def test_mcd_term(self):
        assert is_lcd_query("MCD wound care coverage") is True

    def test_therapy_covered_pattern(self):
        assert is_lcd_query("Is hyperbaric oxygen therapy covered for diabetic wounds?") is True

    def test_coverage_therapy_pattern(self):
        assert is_lcd_query("Medicare coverage for wound care and wound vac therapy") is True

    def test_non_lcd_query(self):
        assert is_lcd_query("What does Medicare Part B cover?") is False

    def test_non_lcd_general(self):
        assert is_lcd_query("HCPCS codes for durable medical equipment") is False

    def test_non_lcd_claims(self):
        assert is_lcd_query("How are Medicare claims processed and submitted?") is False

    def test_non_lcd_denial(self):
        assert is_lcd_query("Common reasons for Medicare claim denials") is False

    def test_case_insensitive(self):
        assert is_lcd_query("lcd coverage for therapy") is True
        assert is_lcd_query("LCD COVERAGE FOR THERAPY") is True


# ---------------------------------------------------------------------------
# LCD query expansion tests
# ---------------------------------------------------------------------------

class TestExpandLcdQuery:

    def test_returns_original_query_first(self):
        queries = expand_lcd_query("LCD for cardiac rehab")
        assert queries[0] == "LCD for cardiac rehab"

    def test_returns_multiple_queries(self):
        queries = expand_lcd_query("LCD for cardiac rehab")
        assert len(queries) >= 2

    def test_cardiac_rehab_expansion(self):
        queries = expand_lcd_query("LCD for cardiac rehab")
        combined = " ".join(queries)
        assert "rehabilitation" in combined.lower()

    def test_hyperbaric_oxygen_expansion(self):
        queries = expand_lcd_query("hyperbaric oxygen for wounds")
        combined = " ".join(queries)
        assert "wound healing" in combined.lower() or "therapy" in combined.lower()

    def test_imaging_expansion(self):
        queries = expand_lcd_query("LCD coverage for advanced imaging MRI")
        combined = " ".join(queries)
        assert "diagnostic" in combined.lower() or "imaging" in combined.lower()

    def test_generic_lcd_expansion(self):
        queries = expand_lcd_query("What LCDs exist for therapy?")
        combined = " ".join(queries)
        assert "local coverage determination" in combined.lower()

    def test_wound_care_expansion(self):
        queries = expand_lcd_query("wound care coverage")
        combined = " ".join(queries)
        assert "wound" in combined.lower()

    def test_includes_stripped_concept_query(self):
        queries = expand_lcd_query(
            "Does Novitas (JL) have an LCD for cardiac rehab?"
        )
        assert len(queries) >= 3
        assert any("cardiac rehab" in q.lower() and "novitas" not in q.lower()
                    for q in queries)


class TestStripToMedicalConcept:

    def test_strips_contractor_and_lcd_terms(self):
        result = _strip_to_medical_concept(
            "Does Novitas (JL) have an LCD for cardiac rehab?"
        )
        assert "novitas" not in result.lower()
        assert "lcd" not in result.lower()
        assert "cardiac rehab" in result.lower()

    def test_strips_ncd_terms(self):
        result = _strip_to_medical_concept(
            "What are the national coverage determination criteria?"
        )
        assert "national coverage determination" not in result.lower()
        assert "criteria" in result.lower()

    def test_preserves_medical_terms(self):
        result = _strip_to_medical_concept(
            "LCD coverage for advanced imaging MRI"
        )
        assert "imaging" in result.lower()
        assert "mri" in result.lower()

    def test_empty_after_strip_returns_empty(self):
        result = _strip_to_medical_concept("LCD NCD MCD")
        assert result == "" or not result.strip()


# ---------------------------------------------------------------------------
# Deduplication tests
# ---------------------------------------------------------------------------

class TestDeduplicateDocs:

    def _make_doc(self, content: str, doc_id: str, chunk: int = 0) -> Document:
        return Document(
            page_content=content,
            metadata={"doc_id": doc_id, "chunk_index": chunk, "source": "mcd"},
        )

    def test_removes_duplicates(self):
        doc_a = self._make_doc("text A", "d1", 0)
        doc_b = self._make_doc("text B", "d2", 0)
        doc_a_dup = self._make_doc("text A copy", "d1", 0)
        result = _deduplicate_docs([[doc_a, doc_b], [doc_a_dup]], max_k=10)
        assert len(result) == 2
        doc_ids = [d.metadata["doc_id"] for d in result]
        assert "d1" in doc_ids
        assert "d2" in doc_ids

    def test_respects_max_k(self):
        docs = [self._make_doc(f"text {i}", f"d{i}", 0) for i in range(10)]
        result = _deduplicate_docs([docs], max_k=3)
        assert len(result) == 3

    def test_preserves_order(self):
        docs = [self._make_doc(f"text {i}", f"d{i}", 0) for i in range(5)]
        result = _deduplicate_docs([docs], max_k=10)
        assert [d.metadata["doc_id"] for d in result] == ["d0", "d1", "d2", "d3", "d4"]

    def test_merges_multiple_lists(self):
        list1 = [self._make_doc("A", "d1", 0), self._make_doc("B", "d2", 0)]
        list2 = [self._make_doc("C", "d3", 0), self._make_doc("D", "d4", 0)]
        result = _deduplicate_docs([list1, list2], max_k=10)
        assert len(result) == 4

    def test_empty_lists(self):
        result = _deduplicate_docs([[], []], max_k=10)
        assert result == []

    def test_different_chunk_indices_not_deduplicated(self):
        doc_a = self._make_doc("text A chunk 0", "d1", 0)
        doc_b = self._make_doc("text A chunk 1", "d1", 1)
        result = _deduplicate_docs([[doc_a, doc_b]], max_k=10)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# LCDAwareRetriever tests (mocked store)
# ---------------------------------------------------------------------------

class TestLCDAwareRetriever:

    def _make_doc(self, content: str, doc_id: str, source: str = "mcd", chunk: int = 0) -> Document:
        return Document(
            page_content=content,
            metadata={"doc_id": doc_id, "chunk_index": chunk, "source": source},
        )

    def _make_mock_store(self) -> MagicMock:
        mock = MagicMock()
        mock.similarity_search.return_value = [
            self._make_doc("LCD cardiac rehab coverage criteria", "mcd_lcd_123"),
        ]
        return mock

    def test_non_lcd_query_uses_standard_search(self):
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(store=store, k=5, lcd_k=12)
        results = retriever.invoke("Medicare Part B coverage")
        assert len(results) == 1
        store.similarity_search.assert_called_once_with(
            "Medicare Part B coverage", k=5
        )

    def test_lcd_query_runs_multiple_searches(self):
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(store=store, k=5, lcd_k=12)
        retriever.invoke("Does Novitas (JL) have an LCD for cardiac rehab?")
        assert store.similarity_search.call_count >= 3

    def test_lcd_query_includes_mcd_filter(self):
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(store=store, k=5, lcd_k=12)
        retriever.invoke("LCD for cardiac rehab")
        calls = store.similarity_search.call_args_list
        mcd_filter_calls = [
            c for c in calls
            if c.kwargs.get("filter", {}).get("source") == "mcd"
        ]
        assert len(mcd_filter_calls) >= 1

    def test_lcd_query_deduplicates_results(self):
        doc = self._make_doc("LCD cardiac rehab", "mcd_1")
        store = MagicMock()
        store.similarity_search.return_value = [doc]
        retriever = LCDAwareRetriever(store=store, k=5, lcd_k=12)
        results = retriever.invoke("LCD cardiac rehab coverage")
        doc_keys = [(d.metadata["doc_id"], d.metadata["chunk_index"]) for d in results]
        assert len(doc_keys) == len(set(doc_keys))

    def test_non_lcd_query_with_metadata_filter(self):
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(
            store=store, k=5, lcd_k=12, metadata_filter={"source": "iom"}
        )
        retriever.invoke("Part B coverage")
        store.similarity_search.assert_called_once_with(
            "Part B coverage", k=5, filter={"source": "iom"}
        )

    def test_lcd_query_with_existing_metadata_filter(self):
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(
            store=store, k=5, lcd_k=12, metadata_filter={"manual": "100-02"}
        )
        retriever.invoke("LCD cardiac rehab coverage")
        calls = store.similarity_search.call_args_list
        mcd_calls = [c for c in calls if "source" in (c.kwargs.get("filter") or {})]
        assert len(mcd_calls) >= 1
        for mc in mcd_calls:
            assert mc.kwargs["filter"]["source"] == "mcd"

    def test_lcd_query_with_non_mcd_source_filter_skips_lcd_aware_retrieval(self):
        """When metadata_filter specifies a non-MCD source, LCD-aware retrieval
        is skipped and standard similarity search is used instead."""
        store = self._make_mock_store()
        retriever = LCDAwareRetriever(
            store=store, k=5, lcd_k=12, metadata_filter={"source": "iom"}
        )
        retriever.invoke("LCD cardiac rehab coverage")
        # Should only make one call with the IOM filter, not multiple MCD calls
        store.similarity_search.assert_called_once_with(
            "LCD cardiac rehab coverage", k=5, filter={"source": "iom"}
        )


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
