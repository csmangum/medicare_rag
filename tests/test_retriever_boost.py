"""Tests for summary document boosting in retrieval (retriever.py)."""
from unittest.mock import MagicMock

from langchain_core.documents import Document

from medicare_rag.query.retriever import (
    LCDAwareRetriever,
    boost_summaries,
    detect_query_topics,
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


class TestLCDAwareRetrieverWithSummaries:

    def _make_mock_store(self, docs: list[Document]) -> MagicMock:
        mock = MagicMock()
        mock.similarity_search.return_value = docs
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
