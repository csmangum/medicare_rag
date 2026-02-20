"""Tests for hybrid retriever, cross-source query expansion, and BM25 index."""

import threading
from unittest.mock import MagicMock, patch

import pytest

from langchain_core.documents import Document

from medicare_rag.query.expand import (
    _apply_synonyms,
    detect_source_relevance,
    expand_cross_source_query,
)
from medicare_rag.query.hybrid import (
    BM25Index,
    HybridRetriever,
    ensure_source_diversity,
    reciprocal_rank_fusion,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _doc(content: str, source: str = "iom", doc_id: str = "d1", chunk: int = 0) -> Document:
    return Document(
        page_content=content,
        metadata={"doc_id": doc_id, "chunk_index": chunk, "source": source},
    )


# ---------------------------------------------------------------------------
# detect_source_relevance
# ---------------------------------------------------------------------------


class TestDetectSourceRelevance:

    def test_iom_signals(self):
        scores = detect_source_relevance("What does Medicare Part B policy say about enrollment?")
        assert scores["iom"] > 0

    def test_mcd_signals(self):
        scores = detect_source_relevance("LCD coverage determination for cardiac rehab")
        assert scores["mcd"] > 0

    def test_codes_signals(self):
        scores = detect_source_relevance("HCPCS procedure codes for infusion therapy")
        assert scores["codes"] > 0

    def test_generic_query_gets_nonzero_for_all(self):
        scores = detect_source_relevance("How are outpatient services handled?")
        assert all(v > 0 for v in scores.values())

    def test_multi_source_query(self):
        scores = detect_source_relevance(
            "What HCPCS codes are used under the LCD for cardiac rehabilitation Part B?"
        )
        assert scores["iom"] > 0
        assert scores["mcd"] > 0
        assert scores["codes"] > 0


# ---------------------------------------------------------------------------
# expand_cross_source_query
# ---------------------------------------------------------------------------


class TestExpandCrossSourceQuery:

    def test_always_includes_original(self):
        variants = expand_cross_source_query("test query")
        assert variants[0] == "test query"

    def test_produces_multiple_variants(self):
        variants = expand_cross_source_query("Medicare coverage for wound care")
        assert len(variants) >= 2

    def test_iom_expansion_present(self):
        variants = expand_cross_source_query("Medicare Part B enrollment guidelines")
        combined = " ".join(variants)
        assert "policy" in combined.lower() or "manual" in combined.lower()

    def test_mcd_expansion_present(self):
        variants = expand_cross_source_query("LCD coverage criteria for imaging")
        combined = " ".join(variants)
        assert "coverage determination" in combined.lower()

    def test_codes_expansion_present(self):
        variants = expand_cross_source_query("HCPCS codes for physical therapy")
        combined = " ".join(variants)
        assert "cpt" in combined.lower() or "icd" in combined.lower()

    def test_synonym_expansion_added(self):
        variants = expand_cross_source_query("wound care coverage billing")
        combined = " ".join(variants)
        assert "reimbursement" in combined.lower() or "claims" in combined.lower()

    def test_generic_query_expands_for_all_sources(self):
        variants = expand_cross_source_query("How are outpatient services handled?")
        assert len(variants) >= 4


# ---------------------------------------------------------------------------
# _apply_synonyms
# ---------------------------------------------------------------------------


class TestApplySynonyms:

    def test_no_match_returns_original(self):
        assert _apply_synonyms("some obscure text") == "some obscure text"

    def test_coverage_expanded(self):
        result = _apply_synonyms("coverage details")
        assert "benefits" in result.lower()

    def test_billing_expanded(self):
        result = _apply_synonyms("billing procedures")
        assert "reimbursement" in result.lower()

    def test_multiple_synonyms(self):
        result = _apply_synonyms("coverage and billing for imaging")
        assert "benefits" in result.lower()
        assert "reimbursement" in result.lower()


# ---------------------------------------------------------------------------
# BM25Index
# ---------------------------------------------------------------------------


class TestBM25Index:

    def _make_collection(self, docs: list[Document]) -> MagicMock:
        ids = [f"id_{i}" for i in range(len(docs))]
        texts = [d.page_content for d in docs]
        metas = [d.metadata for d in docs]
        mock = MagicMock()
        mock.count.return_value = len(docs)
        mock.get.return_value = {
            "ids": ids,
            "documents": texts,
            "metadatas": metas,
        }
        return mock

    def test_build_and_search(self):
        docs = [
            _doc("Medicare Part B outpatient coverage", "iom", "d1"),
            _doc("HCPCS code A1234 infusion therapy", "codes", "d2"),
            _doc("LCD cardiac rehabilitation criteria", "mcd", "d3"),
        ]
        collection = self._make_collection(docs)
        idx = BM25Index()
        idx.ensure_built(collection)
        results = idx.search("cardiac rehabilitation", k=2)
        assert len(results) >= 1
        assert any("cardiac" in r.page_content.lower() for r in results)

    def test_search_with_metadata_filter(self):
        docs = [
            _doc("cardiac rehab coverage", "iom", "d1"),
            _doc("cardiac rehab LCD criteria", "mcd", "d2"),
        ]
        collection = self._make_collection(docs)
        idx = BM25Index()
        idx.ensure_built(collection)
        results = idx.search("cardiac rehab", k=5, metadata_filter={"source": "mcd"})
        assert all(r.metadata.get("source") == "mcd" for r in results)

    def test_empty_collection(self):
        mock = MagicMock()
        mock.count.return_value = 0
        mock.get.return_value = {"ids": [], "documents": [], "metadatas": []}
        idx = BM25Index()
        idx.ensure_built(mock)
        assert idx.search("anything", k=5) == []

    def test_empty_query(self):
        docs = [_doc("Some content", "iom", "d1")]
        collection = self._make_collection(docs)
        idx = BM25Index()
        idx.ensure_built(collection)
        assert idx.search("", k=5) == []

    def test_cache_invalidation(self):
        docs = [_doc("content one", "iom", "d1")]
        collection = self._make_collection(docs)
        idx = BM25Index()
        idx.ensure_built(collection)
        assert idx._doc_count == 1

        docs2 = [_doc("content one", "iom", "d1"), _doc("content two", "mcd", "d2")]
        collection2 = self._make_collection(docs2)
        idx.ensure_built(collection2)
        assert idx._doc_count == 2

    def test_no_rebuild_when_count_matches(self):
        docs = [_doc("content one", "iom", "d1")]
        collection = self._make_collection(docs)
        idx = BM25Index()
        idx.ensure_built(collection)

        collection.get.reset_mock()
        idx.ensure_built(collection)
        collection.get.assert_not_called()

    def test_concurrent_ensure_built(self):
        """Multiple threads calling ensure_built simultaneously build index once."""
        docs = [
            _doc("first doc", "iom", "d1"),
            _doc("second doc", "mcd", "d2"),
            _doc("third doc", "codes", "d3"),
        ]
        collection = self._make_collection(docs)
        idx = BM25Index()
        results: list[list[Document]] = []

        def run_ensure_and_search():
            idx.ensure_built(collection)
            results.append(idx.search("doc", k=3))

        threads = [threading.Thread(target=run_ensure_and_search) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert idx._doc_count == 3
        for r in results:
            assert len(r) >= 1
            assert all("doc" in d.page_content.lower() for d in r)

    def test_bm25_build_with_paginated_collection(self):
        """BM25 index builds correctly when collection.get returns multiple batches."""
        docs = [
            _doc("batch one first", "iom", "d1"),
            _doc("batch one second", "iom", "d2"),
            _doc("batch two first", "mcd", "d3"),
            _doc("batch two second", "mcd", "d4"),
            _doc("unique token xyz", "codes", "d5"),
        ]
        mock = MagicMock()
        mock.count.return_value = 5
        batch_size = 2
        mock.get.side_effect = [
            {
                "ids": [f"id_{i}" for i in range(0, 2)],
                "documents": [docs[i].page_content for i in range(0, 2)],
                "metadatas": [docs[i].metadata for i in range(0, 2)],
            },
            {
                "ids": [f"id_{i}" for i in range(2, 4)],
                "documents": [docs[i].page_content for i in range(2, 4)],
                "metadatas": [docs[i].metadata for i in range(2, 4)],
            },
            {
                "ids": ["id_4"],
                "documents": [docs[4].page_content],
                "metadatas": [docs[4].metadata],
            },
        ]
        idx = BM25Index()
        with patch("medicare_rag.query.hybrid.GET_META_BATCH_SIZE", batch_size):
            idx.ensure_built(mock)
        results = idx.search("xyz", k=5)
        assert len(results) >= 1
        assert any("xyz" in d.page_content for d in results)
        assert idx._doc_count == 5


# ---------------------------------------------------------------------------
# reciprocal_rank_fusion
# ---------------------------------------------------------------------------


class TestReciprocalRankFusion:

    def test_single_list(self):
        docs = [_doc(f"doc {i}", "iom", f"d{i}") for i in range(3)]
        result = reciprocal_rank_fusion([docs])
        assert len(result) == 3
        assert result[0].metadata["doc_id"] == "d0"

    def test_two_lists_same_docs(self):
        docs = [_doc("shared doc", "iom", "d1")]
        result = reciprocal_rank_fusion([docs, docs])
        assert len(result) == 1

    def test_two_lists_different_docs(self):
        list1 = [_doc("doc A", "iom", "dA")]
        list2 = [_doc("doc B", "mcd", "dB")]
        result = reciprocal_rank_fusion([list1, list2])
        assert len(result) == 2

    def test_weights_affect_ranking(self):
        doc_a = _doc("A content", "iom", "dA")
        doc_b = _doc("B content", "mcd", "dB")
        list1 = [doc_a]
        list2 = [doc_b]
        result_a_heavy = reciprocal_rank_fusion(
            [list1, list2], weights=[10.0, 1.0]
        )
        result_b_heavy = reciprocal_rank_fusion(
            [list1, list2], weights=[1.0, 10.0]
        )
        assert result_a_heavy[0].metadata["doc_id"] == "dA"
        assert result_b_heavy[0].metadata["doc_id"] == "dB"

    def test_max_results_respected(self):
        docs = [_doc(f"doc {i}", "iom", f"d{i}") for i in range(10)]
        result = reciprocal_rank_fusion([docs], max_results=3)
        assert len(result) == 3

    def test_empty_lists(self):
        assert reciprocal_rank_fusion([]) == []
        assert reciprocal_rank_fusion([[], []]) == []

    def test_deduplication_across_lists(self):
        doc = _doc("shared", "iom", "d1", chunk=0)
        doc_copy = _doc("shared copy", "iom", "d1", chunk=0)
        result = reciprocal_rank_fusion([[doc], [doc_copy]])
        assert len(result) == 1

    def test_different_chunks_not_deduplicated(self):
        doc1 = _doc("chunk 0", "iom", "d1", chunk=0)
        doc2 = _doc("chunk 1", "iom", "d1", chunk=1)
        result = reciprocal_rank_fusion([[doc1], [doc2]])
        assert len(result) == 2

    def test_rrf_fallback_weight_when_fewer_weights_than_lists(self):
        """When weights has fewer elements than result_lists, missing weights use 1.0."""
        doc_a = _doc("A", "iom", "dA")
        doc_b = _doc("B", "mcd", "dB")
        doc_c = _doc("C", "codes", "dC")
        result = reciprocal_rank_fusion(
            [[doc_a], [doc_b], [doc_c]],
            weights=[10.0],
        )
        assert len(result) == 3
        assert result[0].metadata["doc_id"] == "dA"


# ---------------------------------------------------------------------------
# ensure_source_diversity
# ---------------------------------------------------------------------------


class TestEnsureSourceDiversity:

    def test_no_change_when_single_source_relevant(self):
        docs = [_doc(f"doc {i}", "iom", f"d{i}") for i in range(5)]
        relevance = {"iom": 0.8, "mcd": 0.0, "codes": 0.0}
        result = ensure_source_diversity(docs, relevance, k=5)
        assert len(result) == 5
        assert all(d.metadata["source"] == "iom" for d in result)

    def test_promotes_underrepresented_source(self):
        docs = [
            _doc("iom doc 1", "iom", "d1"),
            _doc("iom doc 2", "iom", "d2"),
            _doc("iom doc 3", "iom", "d3"),
            _doc("iom doc 4", "iom", "d4"),
            _doc("iom doc 5", "iom", "d5"),
            _doc("mcd doc 1", "mcd", "d6"),
            _doc("mcd doc 2", "mcd", "d7"),
        ]
        relevance = {"iom": 0.5, "mcd": 0.5, "codes": 0.0}
        result = ensure_source_diversity(docs, relevance, k=5, min_per_source=2)
        sources = [d.metadata["source"] for d in result]
        assert sources.count("mcd") >= 2

    def test_respects_k_limit(self):
        docs = [_doc(f"doc {i}", "iom", f"d{i}") for i in range(10)]
        relevance = {"iom": 0.5, "mcd": 0.5}
        result = ensure_source_diversity(docs, relevance, k=5)
        assert len(result) <= 5

    def test_empty_docs(self):
        assert ensure_source_diversity([], {"iom": 0.5}, k=5) == []

    def test_empty_relevance(self):
        docs = [_doc("doc", "iom", "d1")]
        result = ensure_source_diversity(docs, {}, k=5)
        assert len(result) == 1

    def test_all_sources_already_present(self):
        docs = [
            _doc("iom doc 1", "iom", "d1"),
            _doc("iom doc 2", "iom", "d2"),
            _doc("mcd doc 1", "mcd", "d3"),
            _doc("mcd doc 2", "mcd", "d4"),
            _doc("codes doc 1", "codes", "d5"),
            _doc("codes doc 2", "codes", "d6"),
        ]
        relevance = {"iom": 0.5, "mcd": 0.5, "codes": 0.5}
        result = ensure_source_diversity(docs, relevance, k=6, min_per_source=2)
        sources = [d.metadata["source"] for d in result]
        assert sources.count("iom") >= 2
        assert sources.count("mcd") >= 2
        assert sources.count("codes") >= 2

    def test_low_relevance_source_not_promoted(self):
        docs = [
            _doc("iom doc 1", "iom", "d1"),
            _doc("iom doc 2", "iom", "d2"),
            _doc("iom doc 3", "iom", "d3"),
            _doc("iom doc 4", "iom", "d4"),
            _doc("codes doc 1", "codes", "d5"),
        ]
        relevance = {"iom": 0.8, "mcd": 0.1, "codes": 0.1}
        result = ensure_source_diversity(docs, relevance, k=4, min_per_source=2)
        sources = [d.metadata["source"] for d in result]
        assert sources.count("iom") >= 2

    def test_summary_doc_not_displaced_by_diversity(self):
        """Topic/document summary at top is not displaced when promoting sources."""
        summary = Document(
            page_content="Cardiac Rehabilitation: consolidated summary.",
            metadata={
                "doc_id": "topic_cardiac_rehab",
                "doc_type": "topic_summary",
                "topic_cluster": "cardiac_rehab",
            },
        )
        docs = [
            summary,
            _doc("iom 1", "iom", "d1"),
            _doc("iom 2", "iom", "d2"),
            _doc("iom 3", "iom", "d3"),
            _doc("iom 4", "iom", "d4"),
            _doc("mcd 1", "mcd", "d5"),
            _doc("mcd 2", "mcd", "d6"),
        ]
        relevance = {"iom": 0.5, "mcd": 0.5, "codes": 0.0}
        result = ensure_source_diversity(docs, relevance, k=5, min_per_source=2)
        summary_docs = [
            d for d in result if d.metadata.get("doc_type") == "topic_summary"
        ]
        assert len(summary_docs) == 1, "topic_summary should remain in result"
        assert result.index(summary_docs[0]) < 3, "summary should remain in top half"

    def test_promo_added_when_last_position_is_summary(self):
        """When the last slot is a summary (cannot be displaced), deficit is still
        filled by displacing the lowest-ranked non-summary doc."""
        summary = Document(
            page_content="Codes summary.",
            metadata={
                "doc_id": "topic_codes",
                "doc_type": "topic_summary",
                "source": "codes",
            },
        )
        docs = [
            _doc("iom 1", "iom", "d1"),
            _doc("iom 2", "iom", "d2"),
            _doc("mcd 1", "mcd", "d3"),
            _doc("mcd 2", "mcd", "d4"),
            summary,
            _doc("codes 1", "codes", "d5"),
        ]
        relevance = {"iom": 0.5, "mcd": 0.5, "codes": 0.5}
        result = ensure_source_diversity(docs, relevance, k=5, min_per_source=2)
        sources = [d.metadata["source"] for d in result]
        assert sources.count("codes") >= 2, "deficit for codes should be filled"
        summary_in = [d for d in result if d.metadata.get("doc_type") == "topic_summary"]
        assert len(summary_in) == 1, "summary should remain (not displaced)"


# ---------------------------------------------------------------------------
# HybridRetriever (mocked store and BM25 index)
# ---------------------------------------------------------------------------


class TestHybridRetriever:

    def _make_mock_store(self, docs: list[Document] | None = None) -> MagicMock:
        if docs is None:
            docs = [
                _doc("Medicare Part B outpatient", "iom", "d1"),
                _doc("LCD cardiac rehab criteria", "mcd", "d2"),
                _doc("HCPCS code A1234", "codes", "d3"),
            ]
        mock = MagicMock()
        mock.similarity_search.return_value = docs

        collection = MagicMock()
        collection.count.return_value = len(docs)
        ids = [f"id_{i}" for i in range(len(docs))]
        texts = [d.page_content for d in docs]
        metas = [d.metadata for d in docs]
        collection.get.return_value = {
            "ids": ids,
            "documents": texts,
            "metadatas": metas,
        }
        mock._collection = collection
        return mock

    def test_returns_results(self):
        store = self._make_mock_store()
        retriever = HybridRetriever(store=store, k=5)
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            results = retriever.invoke("Medicare coverage")
        assert len(results) > 0

    def test_lcd_query_runs_more_searches(self):
        store = self._make_mock_store()
        retriever = HybridRetriever(store=store, k=5, lcd_k=12)
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            retriever.invoke("Medicare Part B")
            non_lcd_calls = store.similarity_search.call_count

            store.similarity_search.reset_mock()
            retriever.invoke("LCD for cardiac rehab")
            lcd_calls = store.similarity_search.call_count

        assert lcd_calls > non_lcd_calls

    def test_metadata_filter_passed_through(self):
        store = self._make_mock_store()
        retriever = HybridRetriever(
            store=store, k=5, metadata_filter={"source": "iom"}
        )
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            retriever.invoke("test query")

        calls = store.similarity_search.call_args_list
        for call in calls:
            filt = call.kwargs.get("filter")
            if filt is not None:
                assert "source" in filt

    def test_handles_empty_store(self):
        store = self._make_mock_store(docs=[])
        store.similarity_search.return_value = []
        retriever = HybridRetriever(store=store, k=5)
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            results = retriever.invoke("any query")
        assert results == []

    def test_deduplicates_results(self):
        doc = _doc("shared content", "iom", "d1")
        store = self._make_mock_store(docs=[doc])
        retriever = HybridRetriever(store=store, k=5)
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            results = retriever.invoke("test query")
        keys = [
            (d.metadata["doc_id"], d.metadata["chunk_index"]) for d in results
        ]
        assert len(keys) == len(set(keys))

    def test_lcd_query_with_source_filter_iom_skips_mcd_boost(self):
        """LCD query with metadata_filter source iom does not add MCD-only searches."""
        store = self._make_mock_store()
        retriever = HybridRetriever(
            store=store, k=5, metadata_filter={"source": "iom"}
        )
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            retriever.invoke("LCD for cardiac rehab")
        for call in store.similarity_search.call_args_list:
            filt = call.kwargs.get("filter")
            if filt is not None:
                assert filt.get("source") != "mcd"

    def test_topic_query_boosts_summary_doc_in_results(self):
        """When query matches a topic, summary docs are boosted and appear in results."""
        regular = _doc("Cardiac rehab coverage criteria", "iom", "d1")
        summary = Document(
            page_content="Cardiac Rehabilitation: consolidated summary.",
            metadata={
                "doc_id": "topic_cardiac_rehab",
                "chunk_index": 0,
                "source": "iom",
                "doc_type": "topic_summary",
                "topic_cluster": "cardiac_rehab",
            },
        )
        store = self._make_mock_store(docs=[regular, summary])
        retriever = HybridRetriever(store=store, k=5)
        with patch("medicare_rag.query.hybrid._bm25_index", new=BM25Index()):
            results = retriever.invoke("cardiac rehab coverage")
        assert any(
            d.metadata.get("doc_type") == "topic_summary" for d in results
        ), "topic_summary doc should appear when query matches topic"


# ---------------------------------------------------------------------------
# Integration: get_retriever returns HybridRetriever when rank-bm25 available
# ---------------------------------------------------------------------------


class TestGetRetrieverIntegration:

    def test_get_retriever_returns_hybrid_when_available(self):
        from medicare_rag.query.retriever import get_retriever

        with patch("medicare_rag.query.hybrid.get_hybrid_retriever") as mock_factory:
            mock_factory.return_value = MagicMock()
            retriever = get_retriever(k=10, metadata_filter={"source": "iom"})

        assert retriever is mock_factory.return_value
        mock_factory.assert_called_once_with(k=10, metadata_filter={"source": "iom"})

    def test_get_hybrid_retriever_raises_when_bm25_unavailable(self):
        """When rank-bm25 is missing, get_hybrid_retriever raises so get_retriever can fall back."""
        from medicare_rag.query.hybrid import get_hybrid_retriever

        with patch("medicare_rag.query.hybrid._HAS_BM25", False):
            with pytest.raises(ImportError, match="rank-bm25 is required for hybrid retrieval"):
                get_hybrid_retriever(k=5)
