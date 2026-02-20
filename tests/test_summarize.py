"""Tests for summarization (ingest/summarize.py)."""

import json
from pathlib import Path

from langchain_core.documents import Document

from medicare_rag.ingest.summarize import (
    _score_sentences,
    _split_sentences,
    generate_all_summaries,
    generate_document_summary,
    generate_topic_summary,
)


def _doc(content: str, source: str = "iom", doc_id: str = "d1", **extra) -> Document:
    meta = {"doc_id": doc_id, "source": source, **extra}
    return Document(page_content=content, metadata=meta)


class TestSplitSentences:

    def test_splits_on_period(self):
        text = "First sentence about coverage. Second sentence about criteria. Third about therapy."
        sents = _split_sentences(text)
        assert len(sents) >= 2

    def test_splits_on_double_newline(self):
        text = "First paragraph about cardiac rehab.\n\nSecond paragraph about wound care."
        sents = _split_sentences(text)
        assert len(sents) == 2

    def test_filters_short_fragments(self):
        text = "A. B. This is a long enough sentence about coverage. C."
        sents = _split_sentences(text)
        assert len(sents) == 1
        assert "long enough" in sents[0]

    def test_empty_input(self):
        assert _split_sentences("") == []

    def test_does_not_split_on_abbreviations(self):
        """Sentence boundary requires capital after period; C.F.R. stays in one piece."""
        text = "e.g. see Section 42. Dr. Smith recommended. C.F.R. § 410 applies."
        sents = _split_sentences(text)
        # We do not split after "e.g." (lowercase "s" follows), so "see Section 42" is not a standalone sentence
        assert not any(s.strip() == "see Section 42" for s in sents)
        # At least one long sentence contains C.F.R. (we did not split on every period in C.F.R.)
        assert any("C.F.R." in s for s in sents)
        assert len(sents) >= 1


class TestScoreSentences:

    def test_returns_top_n(self):
        sentences = [f"Sentence {i} about topic {i % 3} and coverage." for i in range(20)]
        result = _score_sentences(sentences, max_sentences=5)
        assert len(result) == 5

    def test_preserves_original_order(self):
        sentences = [
            "First sentence about cardiac rehabilitation program criteria.",
            "Second sentence about wound care management and therapy.",
            "Third sentence about diagnostic imaging MRI coverage.",
            "Fourth sentence about durable medical equipment wheelchair.",
            "Fifth sentence about home health agency nursing services.",
        ]
        result = _score_sentences(sentences, max_sentences=3)
        indices = [sentences.index(s) for s in result]
        assert indices == sorted(indices)

    def test_empty_input(self):
        assert _score_sentences([]) == []

    def test_fewer_than_max(self):
        sentences = ["One sentence about coverage criteria."]
        result = _score_sentences(sentences, max_sentences=5)
        assert len(result) == 1


class TestGenerateDocumentSummary:

    def test_generates_summary_for_long_doc(self):
        text = ". ".join(
            f"Sentence {i} discusses cardiac rehabilitation coverage criteria and therapy"
            for i in range(20)
        ) + "."
        meta = {"source": "iom", "doc_id": "iom_ch6", "title": "Cardiac Rehab Chapter"}
        summary = generate_document_summary("iom_ch6", text, meta, max_sentences=5)
        assert summary is not None
        assert summary.metadata["doc_type"] == "document_summary"
        assert summary.metadata["doc_id"] == "summary_iom_ch6"
        assert summary.metadata["summary_of"] == "iom_ch6"
        assert "Document summary" in summary.page_content
        assert "iom" in summary.page_content

    def test_returns_none_for_short_text(self):
        summary = generate_document_summary("d1", "Short text.", {})
        assert summary is None

    def test_returns_none_when_few_sentences(self):
        text = "One sentence. Two sentence."
        summary = generate_document_summary("d1", text, {}, max_sentences=5)
        assert summary is None

    def test_preserves_source_metadata(self):
        text = ". ".join(f"Sentence {i} about cardiac rehab" for i in range(20)) + "."
        meta = {"source": "mcd", "doc_id": "mcd_lcd_123", "lcd_id": "L123"}
        summary = generate_document_summary("mcd_lcd_123", text, meta)
        assert summary is not None
        assert summary.metadata["source"] == "mcd"
        assert summary.metadata["lcd_id"] == "L123"


class TestGenerateTopicSummary:

    def test_generates_topic_summary(self):
        chunks = [
            _doc("Cardiac rehabilitation program covers supervised exercise. "
                 "Patients with recent MI or CABG are eligible.", "iom", "d1"),
            _doc("LCD L12345 cardiac rehab coverage criteria include documented "
                 "cardiac diagnosis and physician referral.", "mcd", "d2"),
            _doc("HCPCS codes for cardiac rehab include G0422 and G0423.", "codes", "d3"),
        ]
        summary = generate_topic_summary("cardiac_rehab", chunks, min_chunks=2)
        assert summary is not None
        assert summary.metadata["doc_type"] == "topic_summary"
        assert summary.metadata["topic_cluster"] == "cardiac_rehab"
        assert summary.metadata["topic_label"] == "Cardiac Rehabilitation"
        assert "Cardiac Rehabilitation" in summary.page_content
        assert "consolidated summary" in summary.page_content.lower()

    def test_includes_all_sources(self):
        chunks = [
            _doc("Cardiac rehab IOM content.", "iom", "d1"),
            _doc("Cardiac rehab MCD content.", "mcd", "d2"),
        ]
        summary = generate_topic_summary("cardiac_rehab", chunks, min_chunks=2)
        assert summary is not None
        assert "iom" in summary.metadata["sources_in_cluster"]
        assert "mcd" in summary.metadata["sources_in_cluster"]

    def test_returns_none_for_single_chunk(self):
        chunks = [_doc("Cardiac rehab content.")]
        summary = generate_topic_summary("cardiac_rehab", chunks, min_chunks=2)
        assert summary is None

    def test_returns_none_for_empty_chunks(self):
        summary = generate_topic_summary("cardiac_rehab", [], min_chunks=2)
        assert summary is None

    def test_cluster_size_metadata(self):
        chunks = [_doc(f"Cardiac rehab chunk {i}.", doc_id=f"d{i}") for i in range(5)]
        summary = generate_topic_summary("cardiac_rehab", chunks, min_chunks=2)
        assert summary is not None
        assert summary.metadata["cluster_size"] == 5


class TestGenerateAllSummaries:

    def test_generates_both_summary_types(self):
        long_text = ". ".join(
            f"Sentence {i} about cardiac rehabilitation coverage criteria"
            for i in range(20)
        ) + "."
        doc_texts = [
            (long_text, {"source": "iom", "doc_id": "iom_ch6", "title": "Cardiac Rehab"}),
        ]
        chunks = [
            _doc("cardiac rehab program coverage", "iom", "d1"),
            _doc("cardiac rehabilitation criteria LCD", "mcd", "d2"),
        ]
        tagged, summaries = generate_all_summaries(
            chunks, doc_texts=doc_texts, min_topic_chunks=2,
        )
        assert len(tagged) == 2
        doc_summaries = [s for s in summaries if s.metadata["doc_type"] == "document_summary"]
        topic_summaries = [s for s in summaries if s.metadata["doc_type"] == "topic_summary"]
        assert len(doc_summaries) >= 1
        assert len(topic_summaries) >= 1

    def test_tags_documents_with_topics(self):
        chunks = [
            _doc("cardiac rehab content", doc_id="d1"),
            _doc("generic medicare content", doc_id="d2"),
        ]
        tagged, _ = generate_all_summaries(chunks, min_topic_chunks=999)
        topics_present = [t for t in tagged if "topic_clusters" in t.metadata]
        assert len(topics_present) == 1
        assert "cardiac_rehab" in topics_present[0].metadata["topic_clusters"]

    def test_without_doc_texts(self):
        chunks = [
            _doc("cardiac rehab iom content", "iom", "d1"),
            _doc("cardiac rehab mcd LCD content", "mcd", "d2"),
        ]
        tagged, summaries = generate_all_summaries(chunks, min_topic_chunks=2)
        assert len(tagged) == 2
        topic_summaries = [s for s in summaries if s.metadata["doc_type"] == "topic_summary"]
        assert len(topic_summaries) >= 1

    def test_no_summaries_for_unrelated_chunks(self):
        chunks = [
            _doc("Generic Medicare Part B information", doc_id="d1"),
            _doc("General billing procedures overview", doc_id="d2"),
        ]
        tagged, summaries = generate_all_summaries(chunks, min_topic_chunks=2)
        assert len(summaries) == 0
        assert len(tagged) == 2


class TestChunkDocumentsWithSummaries:

    def test_chunk_documents_with_summaries_enabled(self, tmp_path: Path):
        from medicare_rag.ingest.chunk import chunk_documents

        (tmp_path / "iom" / "100-02").mkdir(parents=True)
        long_text = ". ".join(
            f"Sentence {i} about cardiac rehabilitation coverage criteria and therapy program"
            for i in range(30)
        ) + "."
        (tmp_path / "iom" / "100-02" / "ch6.txt").write_text(long_text)
        (tmp_path / "iom" / "100-02" / "ch6.meta.json").write_text(
            json.dumps({
                "source": "iom",
                "manual": "100-02",
                "chapter": "6",
                "doc_id": "iom_100-02_ch6",
                "title": "Cardiac Rehab",
            })
        )
        docs = chunk_documents(
            tmp_path, source="iom", chunk_size=200, chunk_overlap=50,
            enable_summaries=True,
        )
        summary_docs = [d for d in docs if d.metadata.get("doc_type") in (
            "document_summary", "topic_summary",
        )]
        assert len(summary_docs) >= 1
        regular_docs = [d for d in docs if "doc_type" not in d.metadata]
        assert len(regular_docs) >= 2

    def test_chunk_documents_with_summaries_disabled(self, tmp_path: Path):
        from medicare_rag.ingest.chunk import chunk_documents

        (tmp_path / "iom" / "100-02").mkdir(parents=True)
        long_text = ". ".join(
            f"Sentence {i} about cardiac rehabilitation"
            for i in range(20)
        ) + "."
        (tmp_path / "iom" / "100-02" / "ch6.txt").write_text(long_text)
        (tmp_path / "iom" / "100-02" / "ch6.meta.json").write_text(
            json.dumps({
                "source": "iom",
                "doc_id": "iom_100-02_ch6",
            })
        )
        docs = chunk_documents(
            tmp_path, source="iom", chunk_size=200, chunk_overlap=50,
            enable_summaries=False,
        )
        summary_docs = [d for d in docs if d.metadata.get("doc_type") in (
            "document_summary", "topic_summary",
        )]
        assert len(summary_docs) == 0
