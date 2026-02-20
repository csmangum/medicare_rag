"""Tests for summary document boosting in retrieval (retriever.py)."""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from medicare_rag.query.retriever import (
    LCDAwareRetriever,
    boost_summaries,
    detect_query_topics,
    inject_topic_summaries,
)


def _doc(content: str, source: str = "iom", doc_id: str = "d1",
         chunk: int = 0, **extra) -> Document:
    meta = {"doc_id": doc_id, "chunk_index": chunk, "source": source, **extra}
    return Document(page_content=content, metadata=meta)


class TestDetectQueryTopics:

    def test_cardiac_rehab(self):
        topics = detect_query_topics("What is the LCD for cardiac rehab?")
        assert "cardiac_rehab" in topics

    def test_wound_care(self):
        topics = detect_query_topics("wound care management coverage criteria")
        assert "wound_care" in topics

    def test_multiple_topics(self):
        topics = detect_query_topics("cardiac rehab with physical therapy")
        assert "cardiac_rehab" in topics
        assert "physical_therapy" in topics

    def test_no_topics(self):
        topics = detect_query_topics("What does Medicare Part B cover?")
        assert topics == []

    def test_imaging(self):
        topics = detect_query_topics("MRI coverage criteria")
        assert "imaging" in topics

    def test_hyperbaric(self):
        topics = detect_query_topics("hyperbaric oxygen for wound healing")
        assert "hyperbaric_oxygen" in topics


class TestBoostSummaries:

    def test_topic_summary_promoted_to_top(self):
        regular = _doc("Regular cardiac rehab content", doc_id="d1")
        summary = _doc(
            "Topic summary cardiac rehab",
            doc_id="topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        )
        docs = [regular, summary]
        boosted = boost_summaries(docs, ["cardiac_rehab"], max_k=5)
        assert boosted[0].metadata["doc_id"] == "topic_cardiac_rehab"

    def test_document_summary_with_matching_topic_clusters(self):
        # document_summary docs get topic_clusters from tag_documents_with_topics
        # in generate_all_summaries when their content matches topic patterns
        regular = _doc("Regular content", doc_id="d1")
        summary = _doc(
            "Document summary",
            doc_id="summary_d2",
            doc_type="document_summary",
            topic_clusters="cardiac_rehab,imaging",
        )
        docs = [regular, summary]
        boosted = boost_summaries(docs, ["cardiac_rehab"], max_k=5)
        assert boosted[0].metadata["doc_id"] == "summary_d2"

    def test_no_boost_for_irrelevant_topics(self):
        regular = _doc("Regular content", doc_id="d1")
        summary = _doc(
            "Wound care summary",
            doc_id="topic_wound_care",
            doc_type="topic_summary",
            topic_cluster="wound_care",
        )
        docs = [regular, summary]
        boosted = boost_summaries(docs, ["cardiac_rehab"], max_k=5)
        assert boosted[0].metadata["doc_id"] == "d1"

    def test_respects_max_k(self):
        docs = [_doc(f"content {i}", doc_id=f"d{i}") for i in range(10)]
        docs.append(_doc(
            "summary",
            doc_id="topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        ))
        boosted = boost_summaries(docs, ["cardiac_rehab"], max_k=3)
        assert len(boosted) == 3
        assert boosted[0].metadata["doc_id"] == "topic_cardiac_rehab"

    def test_empty_topics_no_change(self):
        docs = [_doc("content", doc_id="d1")]
        boosted = boost_summaries(docs, [], max_k=5)
        assert len(boosted) == 1

    def test_empty_docs(self):
        boosted = boost_summaries([], ["cardiac_rehab"], max_k=5)
        assert boosted == []

    def test_multiple_summaries_for_same_topic(self):
        regular = _doc("regular content", doc_id="d1")
        s1 = _doc(
            "topic summary", doc_id="topic_cardiac_rehab",
            doc_type="topic_summary", topic_cluster="cardiac_rehab",
        )
        s2 = _doc(
            "doc summary", doc_id="summary_cardiac",
            doc_type="document_summary", topic_clusters="cardiac_rehab",
        )
        docs = [regular, s1, s2]
        boosted = boost_summaries(docs, ["cardiac_rehab"], max_k=5)
        assert all(
            d.metadata.get("doc_type") in ("topic_summary", "document_summary")
            for d in boosted[:2]
        )


class TestInjectTopicSummaries:

    def test_injects_topic_summary_when_topic_exists_and_not_in_docs(self):
        mock_store = MagicMock()
        mock_coll = MagicMock()
        mock_coll.get.return_value = {
            "ids": ["topic_cardiac_rehab"],
            "documents": ["Cardiac rehab consolidated summary."],
            "metadatas": [{
                "doc_id": "topic_cardiac_rehab",
                "doc_type": "topic_summary",
                "topic_cluster": "cardiac_rehab",
            }],
        }
        mock_store._collection = mock_coll

        docs = [_doc("Regular content", doc_id="d1")]
        out = inject_topic_summaries(mock_store, docs, ["cardiac_rehab"], max_k=10)
        assert len(out) == 2
        assert out[0].metadata["doc_id"] == "topic_cardiac_rehab"
        assert out[0].page_content == "Cardiac rehab consolidated summary."
        assert out[1].metadata["doc_id"] == "d1"

    def test_skips_missing_ids_gracefully(self):
        mock_store = MagicMock()
        mock_coll = MagicMock()
        # Chroma returns only ids that exist; topic_nonexistent is missing
        mock_coll.get.return_value = {
            "ids": ["topic_cardiac_rehab"],
            "documents": ["Cardiac rehab summary."],
            "metadatas": [{"doc_id": "topic_cardiac_rehab", "topic_cluster": "cardiac_rehab"}],
        }
        mock_store._collection = mock_coll

        docs = [_doc("content", doc_id="d1")]
        out = inject_topic_summaries(mock_store, docs, ["cardiac_rehab", "nonexistent_topic"], max_k=10)
        assert len(out) == 2
        assert out[0].metadata["doc_id"] == "topic_cardiac_rehab"

    def test_no_duplicate_when_summary_already_in_docs(self):
        mock_store = MagicMock()
        mock_coll = MagicMock()
        mock_coll.get.return_value = {
            "ids": ["topic_cardiac_rehab"],
            "documents": ["Topic summary."],
            "metadatas": [{"doc_id": "topic_cardiac_rehab", "topic_cluster": "cardiac_rehab"}],
        }
        mock_store._collection = mock_coll

        existing_summary = _doc(
            "Topic summary.",
            doc_id="topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        )
        docs = [existing_summary, _doc("Regular", doc_id="d1")]
        out = inject_topic_summaries(mock_store, docs, ["cardiac_rehab"], max_k=10)
        assert len(out) == 2
        assert out[0].metadata["doc_id"] == "topic_cardiac_rehab"
        assert out[1].metadata["doc_id"] == "d1"
        mock_coll.get.assert_called_once()

    def test_empty_topics_returns_docs_unchanged(self):
        mock_store = MagicMock()
        docs = [_doc("content", doc_id="d1")]
        out = inject_topic_summaries(mock_store, docs, [], max_k=10)
        assert out == docs

    def test_respects_max_k(self):
        mock_store = MagicMock()
        mock_coll = MagicMock()
        mock_coll.get.return_value = {
            "ids": ["topic_cardiac_rehab"],
            "documents": ["Summary."],
            "metadatas": [{"doc_id": "topic_cardiac_rehab", "topic_cluster": "cardiac_rehab"}],
        }
        mock_store._collection = mock_coll

        docs = [_doc(f"c{i}", doc_id=f"d{i}") for i in range(5)]
        out = inject_topic_summaries(mock_store, docs, ["cardiac_rehab"], max_k=3)
        assert len(out) == 3
        assert out[0].metadata["doc_id"] == "topic_cardiac_rehab"


class TestLCDAwareRetrieverWithSummaries:

    def _make_mock_store(self, docs: list[Document]) -> MagicMock:
        mock = MagicMock()
        mock.similarity_search.return_value = docs
        # inject_topic_summaries uses get_raw_collection(store)._collection.get()
        mock_coll = MagicMock()
        topic_ids = {d.metadata.get("doc_id") for d in docs if "topic_" in str(d.metadata.get("doc_id", ""))}
        if topic_ids:
            mock_coll.get.return_value = {
                "ids": list(topic_ids),
                "documents": [d.page_content for d in docs if d.metadata.get("doc_id") in topic_ids],
                "metadatas": [d.metadata for d in docs if d.metadata.get("doc_id") in topic_ids],
            }
        else:
            mock_coll.get.return_value = {"ids": [], "documents": [], "metadatas": []}
        mock._collection = mock_coll
        return mock

    def test_non_lcd_query_with_topic_boosts_summaries(self):
        regular = _doc("cardiac rehab criteria", "iom", "d1")
        summary = _doc(
            "Topic summary cardiac rehab",
            "iom",
            "topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        )
        store = self._make_mock_store([regular, summary])
        retriever = LCDAwareRetriever(store=store, k=5)
        results = retriever.invoke("cardiac rehab coverage")
        assert results[0].metadata["doc_id"] == "topic_cardiac_rehab"

    def test_non_topic_query_does_not_boost(self):
        regular = _doc("Medicare Part B coverage", "iom", "d1")
        summary = _doc(
            "Topic summary cardiac rehab",
            "iom",
            "topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        )
        store = self._make_mock_store([regular, summary])
        retriever = LCDAwareRetriever(store=store, k=5)
        results = retriever.invoke("Medicare Part B coverage")
        assert results[0].metadata["doc_id"] == "d1"

    def test_lcd_query_with_topic_boosts_summaries(self):
        regular = _doc("LCD cardiac rehab", "mcd", "d1")
        summary = _doc(
            "Topic summary cardiac rehab",
            "mcd",
            "topic_cardiac_rehab",
            doc_type="topic_summary",
            topic_cluster="cardiac_rehab",
        )
        store = self._make_mock_store([regular, summary])
        retriever = LCDAwareRetriever(store=store, k=5, lcd_k=12)
        results = retriever.invoke("LCD for cardiac rehab")
        summary_docs = [d for d in results if d.metadata.get("doc_type") == "topic_summary"]
        assert len(summary_docs) >= 1

    def test_injection_adds_topic_summary_when_not_in_retrieval(self):
        """When similarity_search returns no topic summary, injection fetches and prepends it."""
        regular_only = [_doc("Regular cardiac rehab content", "iom", "d1")]
        store = MagicMock()
        store.similarity_search.return_value = regular_only
        mock_coll = MagicMock()
        mock_coll.get.return_value = {
            "ids": ["topic_cardiac_rehab"],
            "documents": ["Cardiac rehab consolidated summary."],
            "metadatas": [{
                "doc_id": "topic_cardiac_rehab",
                "doc_type": "topic_summary",
                "topic_cluster": "cardiac_rehab",
            }],
        }
        store._collection = mock_coll

        retriever = LCDAwareRetriever(store=store, k=5)
        results = retriever.invoke("cardiac rehabilitation coverage criteria")
        assert results[0].metadata["doc_id"] == "topic_cardiac_rehab"
        assert "consolidated" in results[0].page_content
