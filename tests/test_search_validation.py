"""Comprehensive tests for search validation and retrieval evaluation (validate_and_eval.py).

Tests cover:
  - DCG/NDCG computation
  - Keyword fraction scoring
  - Relevance scoring (_question_relevance)
  - Per-question evaluation (_evaluate_question) including recall
  - Consistency scoring (_compute_consistency)
  - Full run_eval with mocked retriever (various scenarios)
  - Multi-k sweep
  - Duplicate question ID detection
  - Validation checks (validate_index)
  - Report formatting (text and markdown)
"""
import importlib.util
import json
import math
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

# ---------------------------------------------------------------------------
# Module loading helper (load script as module)
# ---------------------------------------------------------------------------

def _load_module():
    """Load validate_and_eval.py as a module for testing."""
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "validate_and_eval.py"
    spec = importlib.util.spec_from_file_location("validate_and_eval", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return _load_module()


# ---------------------------------------------------------------------------
# DCG / NDCG tests
# ---------------------------------------------------------------------------

class TestDCGAndNDCG:

    def test_dcg_empty(self, mod):
        assert mod._dcg([], 5) == 0.0

    def test_dcg_single_perfect(self, mod):
        assert mod._dcg([1.0], 1) == pytest.approx(1.0 / math.log2(2))

    def test_dcg_two_items(self, mod):
        expected = 1.0 / math.log2(2) + 0.5 / math.log2(3)
        assert mod._dcg([1.0, 0.5], 2) == pytest.approx(expected)

    def test_dcg_respects_k(self, mod):
        # Only first 2 items should be used
        result_k2 = mod._dcg([1.0, 0.5, 1.0], 2)
        result_k3 = mod._dcg([1.0, 0.5, 1.0], 3)
        assert result_k2 < result_k3

    def test_ndcg_perfect_ranking(self, mod):
        # Already in ideal order
        assert mod._ndcg([1.0, 0.5, 0.0], 3) == pytest.approx(1.0)

    def test_ndcg_worst_ranking(self, mod):
        # Worst possible ordering (0, 0.5, 1.0) vs ideal (1.0, 0.5, 0)
        result = mod._ndcg([0.0, 0.5, 1.0], 3)
        assert 0.0 < result < 1.0

    def test_ndcg_all_zero(self, mod):
        assert mod._ndcg([0.0, 0.0, 0.0], 3) == 0.0

    def test_ndcg_all_ones(self, mod):
        # All equally relevant -> always perfect
        assert mod._ndcg([1.0, 1.0, 1.0], 3) == pytest.approx(1.0)

    def test_ndcg_k_larger_than_list(self, mod):
        # k > len(relevances) should still work
        result = mod._ndcg([1.0, 0.5], 10)
        assert result == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Keyword fraction tests
# ---------------------------------------------------------------------------

class TestKeywordFraction:

    def test_no_keywords(self, mod):
        assert mod._keyword_fraction("anything", []) == 1.0

    def test_all_keywords_present(self, mod):
        assert mod._keyword_fraction("Part B outpatient coverage", ["Part B", "outpatient"]) == 1.0

    def test_some_keywords_present(self, mod):
        assert mod._keyword_fraction("Part B details", ["Part B", "outpatient"]) == pytest.approx(0.5)

    def test_no_keywords_present(self, mod):
        assert mod._keyword_fraction("Unrelated text", ["Part B", "outpatient"]) == 0.0

    def test_case_insensitive(self, mod):
        assert mod._keyword_fraction("PART B OUTPATIENT", ["part b", "outpatient"]) == 1.0

    def test_single_keyword_of_four(self, mod):
        result = mod._keyword_fraction("coverage details here", ["Part B", "outpatient", "medical", "coverage"])
        assert result == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Relevance scoring tests
# ---------------------------------------------------------------------------

class TestQuestionRelevance:

    def _make_doc(self, content: str, source: str = "iom") -> Document:
        return Document(page_content=content, metadata={"source": source, "doc_id": "test"})

    def test_full_match_keyword_and_source(self, mod):
        docs = [self._make_doc("Medicare Part B outpatient coverage", "iom")]
        rels = mod._question_relevance(docs, ["Part B", "outpatient"], ["iom"])
        # kw=1.0*0.6 + source=1.0*0.4 = 1.0
        assert rels == [pytest.approx(1.0)]

    def test_keyword_match_wrong_source(self, mod):
        docs = [self._make_doc("Medicare Part B outpatient coverage", "codes")]
        rels = mod._question_relevance(docs, ["Part B"], ["iom"])
        # kw=1.0*0.6 + source=0.0*0.4 = 0.6
        assert rels == [pytest.approx(0.6)]

    def test_source_match_wrong_keyword(self, mod):
        docs = [self._make_doc("Unrelated text about something else", "iom")]
        rels = mod._question_relevance(docs, ["Part B"], ["iom"])
        # kw=0.0*0.6 + source=1.0*0.4 = 0.4
        assert rels == [pytest.approx(0.4)]

    def test_no_match(self, mod):
        docs = [self._make_doc("Completely unrelated content", "codes")]
        rels = mod._question_relevance(docs, ["Part B"], ["iom"])
        # kw=0.0*0.6 + source=0.0*0.4 = 0.0
        assert rels == [pytest.approx(0.0)]

    def test_no_expected_keywords(self, mod):
        # No keyword constraint -> keyword fraction = 1.0
        docs = [self._make_doc("Anything", "iom")]
        rels = mod._question_relevance(docs, None, ["iom"])
        # kw=1.0*0.6 + source=1.0*0.4 = 1.0
        assert rels == [pytest.approx(1.0)]

    def test_no_expected_sources(self, mod):
        # No source constraint -> source = 1.0
        docs = [self._make_doc("Part B coverage", "codes")]
        rels = mod._question_relevance(docs, ["Part B"], None)
        # kw=1.0*0.6 + source=1.0*0.4 = 1.0
        assert rels == [pytest.approx(1.0)]

    def test_no_constraints(self, mod):
        docs = [self._make_doc("Anything", "anything")]
        rels = mod._question_relevance(docs, None, None)
        assert rels == [pytest.approx(1.0)]

    def test_multiple_docs_mixed(self, mod):
        docs = [
            self._make_doc("Part B outpatient", "iom"),     # full match
            self._make_doc("Part B code list", "codes"),     # keyword only
            self._make_doc("IOM general text", "iom"),       # source only
            self._make_doc("Random text", "codes"),          # no match
        ]
        rels = mod._question_relevance(docs, ["Part B"], ["iom"])
        assert rels == [pytest.approx(1.0), pytest.approx(0.6), pytest.approx(0.4), pytest.approx(0.0)]

    def test_keyword_case_insensitive(self, mod):
        docs = [self._make_doc("MEDICARE PART B COVERAGE", "iom")]
        rels = mod._question_relevance(docs, ["part b"], ["iom"])
        assert rels == [pytest.approx(1.0)]

    def test_partial_keyword_match(self, mod):
        """A doc matching 1 of 4 keywords should score lower than one matching all 4."""
        docs = [self._make_doc("coverage details", "iom")]
        rels = mod._question_relevance(docs, ["Part B", "outpatient", "medical", "coverage"], ["iom"])
        # kw=0.25*0.6 + source=1.0*0.4 = 0.55
        assert rels == [pytest.approx(0.55)]

    def test_empty_docs(self, mod):
        rels = mod._question_relevance([], ["Part B"], ["iom"])
        assert rels == []


# ---------------------------------------------------------------------------
# Per-question evaluation tests
# ---------------------------------------------------------------------------

class TestEvaluateQuestion:

    def _make_doc(self, content: str, source: str = "iom", doc_id: str = "test") -> Document:
        return Document(page_content=content, metadata={"source": source, "doc_id": doc_id})

    def test_perfect_single_result(self, mod):
        docs = [self._make_doc("Part B outpatient coverage")]
        result = mod._evaluate_question(docs, ["Part B"], ["iom"], k=5)
        assert result["hit"] is True
        assert result["first_hit_rank"] == 1
        assert result["reciprocal_rank"] == 1.0
        assert result["precision_at_k"] == pytest.approx(1.0 / 5)
        assert result["recall_at_k"] == pytest.approx(1.0)  # iom found
        assert result["ndcg_at_k"] > 0
        assert result["fully_relevant"] == 1

    def test_no_relevant_results(self, mod):
        docs = [self._make_doc("Unrelated content", "codes")]
        result = mod._evaluate_question(docs, ["Part B"], ["iom"], k=5)
        assert result["hit"] is False
        assert result["first_hit_rank"] is None
        assert result["reciprocal_rank"] == 0.0
        assert result["precision_at_k"] == 0.0
        assert result["recall_at_k"] == 0.0
        assert result["fully_relevant"] == 0

    def test_hit_at_rank_3(self, mod):
        docs = [
            self._make_doc("Unrelated", "codes"),
            self._make_doc("Also unrelated", "codes"),
            self._make_doc("Part B coverage info", "iom"),
        ]
        result = mod._evaluate_question(docs, ["Part B"], ["iom"], k=5)
        assert result["hit"] is True
        assert result["first_hit_rank"] == 3
        assert result["reciprocal_rank"] == pytest.approx(1.0 / 3)

    def test_multiple_relevant(self, mod):
        docs = [
            self._make_doc("Part B coverage", "iom"),
            self._make_doc("Part B outpatient", "iom"),
            self._make_doc("Unrelated", "codes"),
        ]
        result = mod._evaluate_question(docs, ["Part B"], ["iom"], k=5)
        assert result["fully_relevant"] == 2
        assert result["precision_at_k"] == pytest.approx(2.0 / 5)

    def test_recall_partial_sources(self, mod):
        """When expecting iom+mcd but only iom retrieved, recall = 0.5."""
        docs = [self._make_doc("Part B coverage details", "iom")]
        result = mod._evaluate_question(docs, ["Part B"], ["iom", "mcd"], k=5)
        assert result["recall_at_k"] == pytest.approx(0.5)

    def test_recall_all_sources(self, mod):
        """When both expected sources are retrieved, recall = 1.0."""
        docs = [
            self._make_doc("Part B coverage", "iom"),
            self._make_doc("Part B coverage MCD", "mcd"),
        ]
        result = mod._evaluate_question(docs, ["Part B"], ["iom", "mcd"], k=5)
        assert result["recall_at_k"] == pytest.approx(1.0)

    def test_source_diversity(self, mod):
        docs = [
            self._make_doc("Content", "iom", "doc1"),
            self._make_doc("Content", "mcd", "doc2"),
            self._make_doc("Content", "codes", "doc3"),
        ]
        result = mod._evaluate_question(docs, None, None, k=5)
        assert set(result["sources_in_topk"]) == {"iom", "mcd", "codes"}

    def test_empty_docs(self, mod):
        result = mod._evaluate_question([], ["Part B"], ["iom"], k=5)
        assert result["hit"] is False
        assert result["precision_at_k"] == 0.0
        assert result["recall_at_k"] == 0.0
        assert result["ndcg_at_k"] == 0.0


# ---------------------------------------------------------------------------
# Consistency scoring tests
# ---------------------------------------------------------------------------

class TestConsistency:

    def test_identical_results(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b", "c"]},
            "q2": {"doc_ids": ["a", "b", "c"]},
        }
        result = mod._compute_consistency(group)
        assert result["score"] == pytest.approx(1.0)

    def test_completely_different(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b"]},
            "q2": {"doc_ids": ["c", "d"]},
        }
        result = mod._compute_consistency(group)
        assert result["score"] == pytest.approx(0.0)

    def test_partial_overlap(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b", "c"]},
            "q2": {"doc_ids": ["b", "c", "d"]},
        }
        result = mod._compute_consistency(group)
        # Jaccard = 2/4 = 0.5
        assert result["score"] == pytest.approx(0.5)

    def test_single_question(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b"]},
        }
        result = mod._compute_consistency(group)
        assert result["score"] == 1.0

    def test_empty_results(self, mod):
        group = {
            "q1": {"doc_ids": []},
            "q2": {"doc_ids": []},
        }
        result = mod._compute_consistency(group)
        assert result["score"] == pytest.approx(1.0)

    def test_one_empty_one_not(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b"]},
            "q2": {"doc_ids": []},
        }
        result = mod._compute_consistency(group)
        assert result["score"] == pytest.approx(0.0)

    def test_three_way(self, mod):
        group = {
            "q1": {"doc_ids": ["a", "b"]},
            "q2": {"doc_ids": ["a", "b"]},
            "q3": {"doc_ids": ["a", "c"]},
        }
        result = mod._compute_consistency(group)
        # q1-q2: 1.0, q1-q3: 1/3, q2-q3: 1/3 -> avg = (1.0 + 1/3 + 1/3) / 3
        expected = (1.0 + 1 / 3 + 1 / 3) / 3
        assert result["score"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Full run_eval tests (with mocked retriever)
# ---------------------------------------------------------------------------

class TestRunEval:

    def _write_eval_file(self, tmp_path: Path, questions: list) -> Path:
        eval_file = tmp_path / "eval.json"
        eval_file.write_text(json.dumps(questions), encoding="utf-8")
        return eval_file

    def _make_doc(self, content: str, source: str = "iom", doc_id: str = "test") -> Document:
        return Document(page_content=content, metadata={"source": source, "doc_id": doc_id})

    def test_single_question_perfect_hit(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "part_b",
                "query": "What does Medicare Part B cover?",
                "expected_keywords": ["Part B", "outpatient"],
                "expected_sources": ["iom"],
                "category": "policy_coverage",
                "difficulty": "easy",
            }
        ])
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            self._make_doc("Medicare Part B covers outpatient medical services."),
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics["n_questions"] == 1
        assert metrics["hit_rate"] == 1.0
        assert metrics["mrr"] == 1.0
        assert metrics["avg_precision_at_k"] == pytest.approx(1.0 / 5)
        assert metrics["avg_ndcg_at_k"] > 0
        assert "latency" in metrics
        assert metrics["latency"]["min_ms"] >= 0
        assert len(metrics["results"]) == 1
        assert metrics["results"][0]["hit"] is True
        assert metrics["results"][0]["first_hit_rank"] == 1

    def test_single_question_miss(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "miss",
                "query": "Something obscure",
                "expected_keywords": ["nonexistent"],
                "expected_sources": ["iom"],
            }
        ])
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            self._make_doc("Unrelated content about something else", "codes"),
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics["hit_rate"] == 0.0
        assert metrics["mrr"] == 0.0
        assert metrics["results"][0]["hit"] is False

    def test_multiple_questions_mixed(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "hit_q",
                "query": "Part B coverage",
                "expected_keywords": ["Part B"],
                "expected_sources": ["iom"],
                "category": "policy_coverage",
                "difficulty": "easy",
            },
            {
                "id": "miss_q",
                "query": "Something else",
                "expected_keywords": ["nonexistent"],
                "expected_sources": ["iom"],
                "category": "code_lookup",
                "difficulty": "hard",
            },
        ])
        mock_retriever = MagicMock()
        # First call is warmup, then one invoke per question.
        mock_retriever.invoke.side_effect = [
            [],  # warmup
            [self._make_doc("Part B outpatient", "iom")],
            [self._make_doc("Unrelated", "codes")],
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics["n_questions"] == 2
        assert metrics["hits"] == 1
        assert metrics["hit_rate"] == pytest.approx(0.5)

    def test_category_breakdown(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "q1",
                "query": "Q1",
                "expected_keywords": ["Part B"],
                "expected_sources": ["iom"],
                "category": "policy_coverage",
                "difficulty": "easy",
            },
            {
                "id": "q2",
                "query": "Q2",
                "expected_keywords": ["code"],
                "expected_sources": ["codes"],
                "category": "code_lookup",
                "difficulty": "hard",
            },
        ])
        mock_retriever = MagicMock()
        # First call is warmup, then one invoke per question.
        mock_retriever.invoke.side_effect = [
            [],  # warmup
            [self._make_doc("Part B text", "iom")],
            [self._make_doc("HCPCS code A1234", "codes", "code_1")],
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert "by_category" in metrics
        assert "policy_coverage" in metrics["by_category"]
        assert "code_lookup" in metrics["by_category"]
        assert metrics["by_category"]["policy_coverage"]["n"] == 1
        assert metrics["by_category"]["code_lookup"]["n"] == 1

    def test_difficulty_breakdown(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "easy_q",
                "query": "Easy question",
                "expected_keywords": ["Part B"],
                "expected_sources": ["iom"],
                "difficulty": "easy",
            },
            {
                "id": "hard_q",
                "query": "Hard question",
                "expected_keywords": ["obscure"],
                "expected_sources": ["mcd"],
                "difficulty": "hard",
            },
        ])
        mock_retriever = MagicMock()
        # First call is warmup, then one invoke per question.
        mock_retriever.invoke.side_effect = [
            [],  # warmup
            [self._make_doc("Part B coverage", "iom")],
            [self._make_doc("Unrelated", "codes")],
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert "by_difficulty" in metrics
        assert "easy" in metrics["by_difficulty"]
        assert "hard" in metrics["by_difficulty"]
        assert metrics["by_difficulty"]["easy"]["hit_rate"] == 1.0
        assert metrics["by_difficulty"]["hard"]["hit_rate"] == 0.0

    def test_consistency_groups(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "c1",
                "query": "cardiac rehab coverage",
                "expected_keywords": ["cardiac"],
                "expected_sources": ["iom"],
                "consistency_group": "cardiac",
            },
            {
                "id": "c2",
                "query": "Does Medicare cover cardiac rehabilitation?",
                "expected_keywords": ["cardiac"],
                "expected_sources": ["iom"],
                "consistency_group": "cardiac",
            },
        ])
        mock_retriever = MagicMock()
        # Return same docs for both queries -> perfect consistency
        mock_retriever.invoke.return_value = [
            self._make_doc("cardiac rehab info", "iom", "doc_cardiac_1"),
            self._make_doc("rehab program details", "iom", "doc_cardiac_2"),
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert "consistency" in metrics
        assert metrics["consistency"]["avg_score"] == pytest.approx(1.0)
        assert "cardiac" in metrics["consistency"]["groups"]

    def test_source_breakdown(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "q1",
                "query": "Coverage",
                "expected_keywords": ["coverage"],
                "expected_sources": ["iom", "mcd"],
            },
        ])
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            self._make_doc("coverage details", "iom"),
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert "by_expected_source" in metrics
        # Question expects iom and mcd, so should appear in both
        assert "iom" in metrics["by_expected_source"]
        assert "mcd" in metrics["by_expected_source"]

    def test_empty_eval_file(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [])

        with patch.object(mod, "_load_retriever", return_value=MagicMock()):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics["n_questions"] == 0

    def test_missing_eval_file(self, mod, tmp_path):
        missing = tmp_path / "nonexistent.json"
        metrics = mod.run_eval(missing, k=5)
        assert metrics == {}

    def test_latency_recorded(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {"id": "q1", "query": "test", "expected_keywords": ["test"]},
        ])
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [self._make_doc("test content")]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics["latency"]["min_ms"] >= 0
        assert metrics["latency"]["max_ms"] >= 0
        assert metrics["latency"]["median_ms"] >= 0
        assert metrics["results"][0]["latency_ms"] >= 0


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

class TestValidateIndex:

    def _make_mock_store(
        self,
        count: int = 12,
        metadatas: list | None = None,
        documents: list | None = None,
        ids: list | None = None,
        embeddings: list | None = None,
    ):
        """Create a mock Chroma store with configurable data.

        By default creates 12 docs with all three sources represented.
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(count)]
        if metadatas is None:
            sources = ["iom"] * 6 + ["mcd"] * 3 + ["codes"] * 3
            metadatas = [
                {"doc_id": f"d{i}", "content_hash": f"hash_{i}", "source": sources[i % len(sources)]}
                for i in range(count)
            ]
        if documents is None:
            documents = [f"Document content {i}" for i in range(count)]
        if embeddings is None:
            embeddings = [[0.1] * 384 for _ in range(count)]

        mock_collection = MagicMock()
        mock_collection.count.return_value = count
        mock_collection.get.side_effect = lambda **kwargs: {
            "ids": ids,
            "metadatas": metadatas if "metadatas" in kwargs.get("include", []) else None,
            "documents": documents if "documents" in kwargs.get("include", []) else None,
            "embeddings": embeddings if "embeddings" in kwargs.get("include", []) else None,
        }

        def _sim_search(query, k=3, filter=None):
            src = filter.get("source", "iom") if filter else "iom"
            return [
                Document(page_content=f"result for {query}", metadata={"source": src, "doc_id": "d1"}),
            ]

        mock_store = MagicMock()
        mock_store._collection = mock_collection
        mock_store.similarity_search.side_effect = _sim_search
        return mock_store

    def test_validation_passes_healthy_index(self, mod, tmp_path):
        store = self._make_mock_store()
        with patch("medicare_rag.config.CHROMA_DIR", tmp_path), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            tmp_path.mkdir(exist_ok=True)
            result = mod.validate_index(store)

        assert result["passed"] is True
        assert result["stats"]["total_documents"] == 12

    def test_validation_fails_missing_dir(self, mod, tmp_path):
        store = self._make_mock_store()
        missing = tmp_path / "nonexistent"
        with patch("medicare_rag.config.CHROMA_DIR", missing), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            result = mod.validate_index(store)

        assert result["passed"] is False

    def test_validation_fails_empty_collection(self, mod, tmp_path):
        store = self._make_mock_store(count=0, ids=[], metadatas=[], documents=[])
        with patch("medicare_rag.config.CHROMA_DIR", tmp_path), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            tmp_path.mkdir(exist_ok=True)
            result = mod.validate_index(store)

        assert result["passed"] is False

    def test_validation_detects_missing_metadata(self, mod, tmp_path):
        metadatas = [
            {"source": "iom"},  # missing doc_id and content_hash
        ]
        store = self._make_mock_store(count=1, ids=["d1"], metadatas=metadatas, documents=["text"])
        with patch("medicare_rag.config.CHROMA_DIR", tmp_path), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            tmp_path.mkdir(exist_ok=True)
            result = mod.validate_index(store)

        assert result["passed"] is False
        failed_names = [c["name"] for c in result["checks"] if not c["passed"]]
        assert "metadata_key_doc_id" in failed_names
        assert "metadata_key_content_hash" in failed_names

    def test_validation_reports_source_distribution(self, mod, tmp_path):
        metadatas = [
            {"doc_id": "d1", "content_hash": "h1", "source": "iom"},
            {"doc_id": "d2", "content_hash": "h2", "source": "iom"},
            {"doc_id": "d3", "content_hash": "h3", "source": "mcd"},
            {"doc_id": "d4", "content_hash": "h4", "source": "codes"},
        ]
        store = self._make_mock_store(
            count=4,
            ids=["d1", "d2", "d3", "d4"],
            metadatas=metadatas,
            documents=["t1", "t2", "t3", "t4"],
        )
        with patch("medicare_rag.config.CHROMA_DIR", tmp_path), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            tmp_path.mkdir(exist_ok=True)
            result = mod.validate_index(store)

        assert result["stats"]["source_distribution"] == {"iom": 2, "mcd": 1, "codes": 1}

    def test_validation_detects_empty_documents(self, mod, tmp_path):
        store = self._make_mock_store(
            count=2,
            ids=["d1", "d2"],
            metadatas=[
                {"doc_id": "d1", "content_hash": "h1", "source": "iom"},
                {"doc_id": "d2", "content_hash": "h2", "source": "iom"},
            ],
            documents=["Normal content", ""],
            embeddings=[[0.1] * 384, [0.2] * 384],
        )
        with patch("medicare_rag.config.CHROMA_DIR", tmp_path), \
             patch("medicare_rag.config.COLLECTION_NAME", "test"):
            tmp_path.mkdir(exist_ok=True)
            result = mod.validate_index(store)

        # Should fail due to empty documents (and possibly missing sources)
        failed_names = [c["name"] for c in result["checks"] if not c["passed"]]
        assert "no_empty_documents" in failed_names


# ---------------------------------------------------------------------------
# Report formatting tests
# ---------------------------------------------------------------------------

class TestReportFormatting:

    def test_format_report_not_empty(self, mod):
        metrics = {
            "n_questions": 2,
            "k": 5,
            "hit_rate": 0.5,
            "hits": 1,
            "mrr": 0.5,
            "avg_precision_at_k": 0.1,
            "avg_recall_at_k": 0.5,
            "avg_ndcg_at_k": 0.3,
            "latency": {
                "min_ms": 10, "max_ms": 50, "median_ms": 25,
                "mean_ms": 30, "p95_ms": 48, "p99_ms": 50,
            },
            "by_category": {
                "policy": {"n": 1, "hit_rate": 1.0, "mrr": 1.0, "avg_precision_at_k": 0.2, "avg_recall_at_k": 0.5, "avg_ndcg_at_k": 0.5},
            },
            "by_difficulty": {
                "easy": {"n": 1, "hit_rate": 1.0, "mrr": 1.0, "avg_precision_at_k": 0.2, "avg_recall_at_k": 0.5, "avg_ndcg_at_k": 0.5},
            },
            "by_expected_source": {
                "iom": {"n": 1, "hit_rate": 1.0, "mrr": 1.0, "avg_precision_at_k": 0.2, "avg_recall_at_k": 0.5, "avg_ndcg_at_k": 0.5},
            },
            "consistency": {"avg_score": 0.8, "groups": {}},
            "multi_k": None,
            "results": [
                {
                    "id": "q1", "query": "test", "category": "policy", "difficulty": "easy",
                    "latency_ms": 25.0, "hit": True, "first_hit_rank": 1,
                    "reciprocal_rank": 1.0, "precision_at_k": 0.2, "recall_at_k": 0.5,
                    "ndcg_at_k": 0.5,
                    "fully_relevant": 1, "partially_relevant": 0, "sources_in_topk": ["iom"],
                },
            ],
        }
        lines = mod._format_report(metrics)
        assert len(lines) > 5
        assert any("Hit Rate" in l for l in lines)
        assert any("MRR" in l for l in lines)
        assert any("NDCG" in l for l in lines)
        assert any("Category" in l for l in lines)
        assert any("Difficulty" in l for l in lines)

    def test_format_validation_report_not_empty(self, mod):
        validation = {
            "passed": True,
            "checks": [
                {"name": "test_check", "passed": True, "detail": "ok"},
            ],
            "stats": {
                "checks_passed": 1,
                "checks_total": 1,
                "total_documents": 100,
                "source_distribution": {"iom": 50, "mcd": 30, "codes": 20},
                "content_length": {
                    "min": 10, "max": 5000, "median": 800, "mean": 900,
                    "p5": 50, "p95": 3000,
                },
                "embedding_dimension": 384,
                "metadata_keys": {"doc_id": 100, "source": 100},
            },
            "warnings": [],
        }
        lines = mod._format_validation_report(validation)
        assert len(lines) > 3
        assert any("100" in l for l in lines)


# ---------------------------------------------------------------------------
# Eval questions file schema test
# ---------------------------------------------------------------------------

class TestEvalQuestionsSchema:

    def test_eval_questions_are_valid_json(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)
        assert isinstance(questions, list)
        assert len(questions) > 0

    def test_eval_questions_have_required_fields(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)

        required_fields = {"id", "query"}
        for q in questions:
            for field in required_fields:
                assert field in q, f"Question missing required field '{field}': {q.get('id', '?')}"
            assert isinstance(q["query"], str)
            assert len(q["query"]) > 0

    def test_eval_questions_ids_are_unique(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)

        ids = [q["id"] for q in questions]
        assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[i for i in ids if ids.count(i) > 1]}"

    def test_eval_questions_have_categories(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)

        for q in questions:
            assert "category" in q, f"Question {q['id']} missing category"
            assert "difficulty" in q, f"Question {q['id']} missing difficulty"

    def test_eval_questions_have_enough_variety(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)

        categories = set(q.get("category") for q in questions)
        difficulties = set(q.get("difficulty") for q in questions)
        assert len(categories) >= 5, f"Need at least 5 categories, got {len(categories)}: {categories}"
        assert len(difficulties) >= 2, f"Need at least 2 difficulty levels, got {len(difficulties)}"
        assert len(questions) >= 30, f"Need at least 30 questions, got {len(questions)}"

    def test_consistency_groups_have_pairs(self):
        eval_path = Path(__file__).resolve().parent.parent / "scripts" / "eval_questions.json"
        with open(eval_path, encoding="utf-8") as f:
            questions = json.load(f)

        groups: dict[str, int] = {}
        for q in questions:
            g = q.get("consistency_group")
            if g:
                groups[g] = groups.get(g, 0) + 1

        for group, count in groups.items():
            assert count >= 2, f"Consistency group '{group}' has only {count} question(s)"


# ---------------------------------------------------------------------------
# Multi-k sweep test
# ---------------------------------------------------------------------------

class TestMultiKSweep:

    def _write_eval_file(self, tmp_path: Path, questions: list) -> Path:
        eval_file = tmp_path / "eval.json"
        eval_file.write_text(json.dumps(questions), encoding="utf-8")
        return eval_file

    def _make_doc(self, content: str, source: str = "iom", doc_id: str = "test") -> Document:
        return Document(page_content=content, metadata={"source": source, "doc_id": doc_id})

    def test_multi_k_sweep_produces_metrics(self, mod, tmp_path):
        eval_file = self._write_eval_file(tmp_path, [
            {
                "id": "q1",
                "query": "Part B coverage",
                "expected_keywords": ["Part B"],
                "expected_sources": ["iom"],
            }
        ])
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [
            self._make_doc("Part B outpatient info", "iom", "d1"),
            self._make_doc("Part B billing", "iom", "d2"),
            self._make_doc("Unrelated", "codes", "d3"),
        ]

        with patch.object(mod, "_load_retriever", return_value=mock_retriever):
            metrics = mod.run_eval(eval_file, k=3, k_values=[1, 3])

        assert metrics["multi_k"] is not None
        assert 1 in metrics["multi_k"]
        assert 3 in metrics["multi_k"]
        # k=1 should have 1 hit (first doc is relevant), k=3 also
        assert metrics["multi_k"][1]["hit_rate"] == 1.0
        assert metrics["multi_k"][3]["hit_rate"] == 1.0
        # Precision should differ: 1/1=1.0 at k=1, 2/3 at k=3
        assert metrics["multi_k"][1]["avg_precision_at_k"] >= metrics["multi_k"][3]["avg_precision_at_k"]
        # Recall should be present
        assert "avg_recall_at_k" in metrics["multi_k"][1]


# ---------------------------------------------------------------------------
# Duplicate question ID detection test
# ---------------------------------------------------------------------------

class TestDuplicateQuestionIdDetection:

    def test_duplicate_ids_return_error(self, mod, tmp_path):
        eval_file = tmp_path / "dup.json"
        eval_file.write_text(json.dumps([
            {"id": "same_id", "query": "Q1", "expected_keywords": ["test"]},
            {"id": "same_id", "query": "Q2", "expected_keywords": ["test"]},
        ]), encoding="utf-8")

        with patch.object(mod, "_load_retriever", return_value=MagicMock()):
            metrics = mod.run_eval(eval_file, k=5)

        assert metrics.get("error") == "duplicate_question_ids"
        assert metrics["n_questions"] == 0


# ---------------------------------------------------------------------------
# Markdown report builder test
# ---------------------------------------------------------------------------

class TestMarkdownReportBuilder:

    def test_build_markdown_report_validation_only(self, mod):
        validation = {
            "passed": True,
            "checks": [{"name": "test", "passed": True, "detail": "ok"}],
            "stats": {
                "checks_passed": 1,
                "checks_total": 1,
                "total_documents": 100,
                "source_distribution": {"iom": 60, "mcd": 30, "codes": 10},
                "content_length": {"min": 5, "max": 4000, "median": 500, "mean": 600, "p5": 50, "p95": 2000},
                "embedding_dimension": 384,
            },
            "warnings": [],
        }
        md = mod._build_markdown_report(validation, None, k=5)
        assert "## Index Validation" in md
        assert "PASSED" in md
        assert "384" in md

    def test_build_markdown_report_eval_only(self, mod):
        metrics = {
            "n_questions": 2,
            "k": 5,
            "hit_rate": 0.5,
            "hits": 1,
            "mrr": 0.5,
            "avg_precision_at_k": 0.2,
            "avg_recall_at_k": 0.5,
            "avg_ndcg_at_k": 0.4,
            "latency": {"min_ms": 5, "max_ms": 20, "median_ms": 10, "mean_ms": 12, "p95_ms": 18, "p99_ms": 20},
            "by_category": {},
            "by_difficulty": {},
            "by_expected_source": {},
            "consistency": {"avg_score": None, "groups": {}},
            "multi_k": None,
            "results": [
                {
                    "id": "q1", "hit": True, "first_hit_rank": 1, "precision_at_k": 0.2,
                    "recall_at_k": 1.0, "ndcg_at_k": 0.5, "category": "test", "difficulty": "easy",
                },
            ],
        }
        md = mod._build_markdown_report(None, metrics, k=5)
        assert "## Retrieval Evaluation" in md
        assert "Recall" in md
        assert "Hit rate" in md

    def test_build_markdown_report_both(self, mod):
        validation = {
            "passed": False,
            "checks": [
                {"name": "test_ok", "passed": True, "detail": "ok"},
                {"name": "test_fail", "passed": False, "detail": "missing data"},
            ],
            "stats": {"checks_passed": 1, "checks_total": 2, "total_documents": 50},
            "warnings": ["something"],
        }
        metrics = {
            "n_questions": 1,
            "k": 5,
            "hit_rate": 1.0,
            "hits": 1,
            "mrr": 1.0,
            "avg_precision_at_k": 0.2,
            "avg_recall_at_k": 1.0,
            "avg_ndcg_at_k": 1.0,
            "latency": {"min_ms": 5, "max_ms": 5, "median_ms": 5, "mean_ms": 5, "p95_ms": 5, "p99_ms": 5},
            "by_category": {},
            "by_difficulty": {},
            "by_expected_source": {},
            "consistency": {"avg_score": None, "groups": {}},
            "multi_k": None,
            "results": [
                {
                    "id": "q1", "hit": True, "first_hit_rank": 1, "precision_at_k": 0.2,
                    "recall_at_k": 1.0, "ndcg_at_k": 1.0, "category": "test", "difficulty": "easy",
                },
            ],
        }
        md = mod._build_markdown_report(validation, metrics, k=5)
        assert "## Index Validation" in md
        assert "FAILED" in md
        assert "Failed checks" in md
        assert "## Retrieval Evaluation" in md
