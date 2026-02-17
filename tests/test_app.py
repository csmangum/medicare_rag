"""Tests for Streamlit app helpers (embedding search UI)."""
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
