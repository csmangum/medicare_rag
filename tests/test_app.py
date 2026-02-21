"""Tests for Streamlit app helpers (embedding search UI)."""
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("streamlit")

import app


class TestEscape:
    def test_escapes_ampersand(self) -> None:
        assert app._escape("a & b") == "a &amp; b"

    def test_escapes_less_than(self) -> None:
        assert app._escape("<script>") == "&lt;script&gt;"

    def test_escapes_greater_than(self) -> None:
        assert app._escape(">") == "&gt;"

    def test_escapes_double_quote(self) -> None:
        assert app._escape('say "hi"') == "say &quot;hi&quot;"

    def test_escapes_single_quote(self) -> None:
        # html.escape(quote=True) uses &#x27; for apostrophe
        assert app._escape("it's") == "it&#x27;s"

    def test_escapes_multiple(self) -> None:
        assert app._escape('& < " \'') == "&amp; &lt; &quot; &#x27;"


class TestBuildMetadataFilter:
    def test_no_filters_returns_none(self) -> None:
        assert app._build_metadata_filter("", "", "") is None
        assert app._build_metadata_filter("All", "All", "All") is None

    def test_single_filter_source(self) -> None:
        assert app._build_metadata_filter("IOM", "All", "All") == {"source": "iom"}

    def test_single_filter_manual(self) -> None:
        assert app._build_metadata_filter("All", "100-02", "All") == {"manual": "100-02"}

    def test_single_filter_jurisdiction(self) -> None:
        assert app._build_metadata_filter("All", "All", "J-A") == {"jurisdiction": "J-A"}

    def test_multiple_filters_returns_and(self) -> None:
        result = app._build_metadata_filter("IOM", "100-02", "J-A")
        assert result == {
            "$and": [
                {"source": "iom"},
                {"manual": "100-02"},
                {"jurisdiction": "J-A"},
            ]
        }

    def test_source_lowercased(self) -> None:
        assert app._build_metadata_filter("MCD", "All", "All") == {"source": "mcd"}


class TestGetCollectionMeta:
    def test_empty_collection_returns_zeros_and_empty_lists(self) -> None:
        app._get_collection_meta.clear()

        class MockCollection:
            def count(self):
                return 0

        class MockStore:
            _collection = MockCollection()

        result = app._get_collection_meta(MockStore())
        assert result == {
            "count": 0,
            "sources": [],
            "manuals": [],
            "jurisdictions": [],
        }

    def test_single_batch_aggregates_metadata(self) -> None:
        app._get_collection_meta.clear()

        class MockCollection:
            def count(self):
                return 2

            def get(self, include=None, limit=None, offset=0):
                if offset == 0:
                    return {
                        "metadatas": [
                            {"source": "iom", "manual": "100-02", "jurisdiction": "J-A"},
                            {"source": "mcd", "manual": "L12345"},
                        ]
                    }
                return {"metadatas": []}

        class MockStore:
            _collection = MockCollection()

        result = app._get_collection_meta(MockStore())
        assert result["count"] == 2
        assert result["sources"] == ["iom", "mcd"]
        assert result["manuals"] == ["100-02", "L12345"]
        assert result["jurisdictions"] == ["J-A"]

    def test_multiple_batches_aggregates_and_dedupes(self) -> None:
        app._get_collection_meta.clear()

        class MockCollection:
            def count(self):
                return 600

            def get(self, include=None, limit=None, offset=0):
                if offset == 0:
                    return {
                        "metadatas": [
                            {"source": "iom", "manual": "100-02"},
                            {"source": "iom", "manual": "100-03"},
                        ]
                        + [{"source": "mcd"} for _ in range(498)],
                    }
                if offset == 500:
                    return {
                        "metadatas": [
                            {"source": "mcd", "jurisdiction": "J-B"},
                            {"source": "codes"},
                        ]
                        + [{} for _ in range(98)],
                    }
                return {"metadatas": []}

        class MockStore:
            _collection = MockCollection()

        result = app._get_collection_meta(MockStore())
        assert result["count"] == 600
        assert sorted(result["sources"]) == ["codes", "iom", "mcd"]
        assert sorted(result["manuals"]) == ["100-02", "100-03"]
        assert result["jurisdictions"] == ["J-B"]


class TestRunHybridSearch:
    def test_returns_retriever_results(self) -> None:
        fake_docs = [MagicMock(), MagicMock()]
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = fake_docs

        with patch.object(app, "get_retriever", return_value=mock_retriever):
            result = app._run_hybrid_search("Medicare timely filing", k=5, metadata_filter=None)

        mock_retriever.invoke.assert_called_once_with("Medicare timely filing")
        assert result == fake_docs

    def test_passes_k_and_filter_to_retriever_factory(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []
        flt = {"source": "iom"}

        with patch.object(app, "get_retriever", return_value=mock_retriever) as mock_get:
            app._run_hybrid_search("query", k=3, metadata_filter=flt)

        mock_get.assert_called_once_with(k=3, metadata_filter=flt)

    def test_returns_empty_list_when_no_results(self) -> None:
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []

        with patch.object(app, "get_retriever", return_value=mock_retriever):
            result = app._run_hybrid_search("no match query", k=10, metadata_filter=None)

        assert result == []


class TestRunRawSearch:
    def _make_store(self, docs_with_scores):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = docs_with_scores
        return mock_store

    def test_returns_all_results_without_threshold(self) -> None:
        doc1, doc2 = MagicMock(), MagicMock()
        store = self._make_store([(doc1, 0.5), (doc2, 1.2)])

        result = app._run_raw_search(store, "query", k=5, metadata_filter=None, score_threshold=None)

        assert result == [(doc1, 0.5), (doc2, 1.2)]
        store.similarity_search_with_score.assert_called_once_with("query", k=5)

    def test_applies_score_threshold(self) -> None:
        doc1, doc2, doc3 = MagicMock(), MagicMock(), MagicMock()
        store = self._make_store([(doc1, 0.3), (doc2, 0.8), (doc3, 1.5)])

        result = app._run_raw_search(store, "query", k=5, metadata_filter=None, score_threshold=0.9)

        assert result == [(doc1, 0.3), (doc2, 0.8)]

    def test_passes_metadata_filter(self) -> None:
        store = self._make_store([])
        flt = {"source": "mcd"}

        app._run_raw_search(store, "query", k=3, metadata_filter=flt, score_threshold=None)

        store.similarity_search_with_score.assert_called_once_with("query", k=3, filter=flt)

    def test_returns_empty_list_when_all_filtered_by_threshold(self) -> None:
        doc = MagicMock()
        store = self._make_store([(doc, 1.9)])

        result = app._run_raw_search(store, "query", k=5, metadata_filter=None, score_threshold=0.5)

        assert result == []
