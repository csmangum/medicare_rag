"""Extractive summarization for document-level and topic-cluster summaries.

Generates summary documents that consolidate key content from fragmented
sources, improving retrieval stability across query rephrasings.  Uses a
simple TF-IDF-like sentence scoring approach so no external LLM or API
is needed at ingest time.
"""

import logging
import math
import re
from collections import Counter

from langchain_core.documents import Document

from medicare_rag.ingest.cluster import (
    cluster_documents,
    get_topic_def,
    tag_documents_with_topics,
)

logger = logging.getLogger(__name__)

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n{2,}")
_WORD_RE = re.compile(r"\w+")

_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "this", "that",
    "these", "those", "it", "its", "not", "no", "nor", "as", "if", "then",
    "than", "so", "such", "each", "every", "all", "any", "both", "few",
    "more", "most", "other", "some", "only", "own", "same", "very",
})


def _tokenize_lower(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS]


def _split_sentences(text: str) -> list[str]:
    raw = _SENTENCE_RE.split(text)
    sentences: list[str] = []
    for s in raw:
        s = s.strip()
        if len(s) > 20:
            sentences.append(s)
    return sentences


def _score_sentences(
    sentences: list[str],
    *,
    max_sentences: int = 10,
) -> list[str]:
    """Score sentences by TF-IDF-like importance and return the top ones
    in their original order."""
    if not sentences:
        return []

    doc_freq: Counter[str] = Counter()
    sent_tfs: list[Counter[str]] = []
    n_sentences = len(sentences)

    for sent in sentences:
        tokens = _tokenize_lower(sent)
        tf = Counter(tokens)
        sent_tfs.append(tf)
        doc_freq.update(set(tokens))

    scored: list[tuple[float, int, str]] = []
    for i, (sent, tf) in enumerate(zip(sentences, sent_tfs, strict=True)):
        score = 0.0
        for term, count in tf.items():
            df = doc_freq.get(term, 1)
            idf = math.log(1 + n_sentences / df)
            score += count * idf
        length_norm = max(1, len(_WORD_RE.findall(sent)))
        score /= length_norm
        # Small positional bonus for earlier sentences (often more important)
        position_bonus = 1.0 + 0.1 * max(0, 1.0 - i / max(1, n_sentences))
        score *= position_bonus
        scored.append((score, i, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_indices = sorted(i for _, i, _ in scored[:max_sentences])
    return [sentences[i] for i in top_indices]


def generate_document_summary(
    doc_id: str,
    full_text: str,
    metadata: dict,
    *,
    max_sentences: int = 8,
    min_text_length: int = 200,
) -> Document | None:
    """Generate an extractive summary Document for a single source document.

    Returns None if the text is too short to warrant a separate summary.
    """
    if len(full_text.strip()) < min_text_length:
        return None

    sentences = _split_sentences(full_text)
    if len(sentences) <= max_sentences:
        return None

    top_sentences = _score_sentences(sentences, max_sentences=max_sentences)
    if not top_sentences:
        return None

    summary_text = " ".join(top_sentences)

    title = metadata.get("title") or doc_id
    source = metadata.get("source", "unknown")
    prefix = f"Document summary ({source}): {title}. "

    summary_meta = {
        k: v for k, v in metadata.items()
        if v is not None and isinstance(v, (str, int, float, bool))
    }
    summary_meta["doc_type"] = "document_summary"
    summary_meta["doc_id"] = f"summary_{doc_id}"
    summary_meta["summary_of"] = doc_id

    return Document(
        page_content=prefix + summary_text,
        metadata=summary_meta,
    )


def generate_topic_summary(
    topic_name: str,
    chunks: list[Document],
    *,
    max_sentences: int = 10,
    min_chunks: int = 2,
) -> Document | None:
    """Generate a consolidated summary for a topic cluster.

    Merges the most important sentences across all chunks belonging to
    the topic, creating a single summary document that captures the
    topic's coverage across multiple source types.

    Returns None if fewer than *min_chunks* chunks belong to the topic.
    """
    if len(chunks) < min_chunks:
        return None

    topic_def = get_topic_def(topic_name)
    label = topic_def.label if topic_def else topic_name
    prefix = topic_def.summary_prefix if topic_def else f"{topic_name}: "

    all_text = "\n\n".join(c.page_content for c in chunks)
    sentences = _split_sentences(all_text)

    if not sentences:
        return None

    top_sentences = _score_sentences(sentences, max_sentences=max_sentences)
    if not top_sentences:
        return None

    summary_text = " ".join(top_sentences)

    sources_in_cluster = sorted({
        c.metadata.get("source", "unknown") for c in chunks
    })
    doc_ids_in_cluster = sorted({
        c.metadata.get("doc_id", "") for c in chunks
    })

    # Avoid duplicating the topic label when summary_prefix already includes it
    if topic_def and topic_def.summary_prefix:
        header = (
            f"{prefix}Consolidated summary across "
            f"{len(chunks)} chunks from {', '.join(sources_in_cluster)}. "
        )
    else:
        header = (
            f"{label} — consolidated summary across "
            f"{len(chunks)} chunks from {', '.join(sources_in_cluster)}. "
        )
    return Document(
        page_content=header + summary_text,
        metadata={
            "doc_type": "topic_summary",
            "doc_id": f"topic_{topic_name}",
            "topic_cluster": topic_name,
            "topic_label": label,
            "sources_in_cluster": ",".join(sources_in_cluster),
            "cluster_size": len(chunks),
            "cluster_total_doc_ids": len(doc_ids_in_cluster),
            "cluster_doc_ids": ",".join(doc_ids_in_cluster[:20]),
        },
    )


def generate_all_summaries(
    documents: list[Document],
    doc_texts: list[tuple[str, dict]] | None = None,
    *,
    max_doc_summary_sentences: int = 8,
    max_topic_summary_sentences: int = 10,
    min_topic_chunks: int = 2,
    min_doc_text_length: int = 200,
) -> tuple[list[Document], list[Document]]:
    """Generate document-level and topic-cluster summaries.

    Parameters
    ----------
    documents:
        Chunked documents (already split by the chunker).
    doc_texts:
        Optional list of (full_text, metadata) tuples from the extraction
        phase.  When provided, document-level summaries are generated
        from the full text rather than from chunks.

    Returns
    -------
    (tagged_documents, summary_documents):
        tagged_documents — the input documents with ``topic_clusters``
        metadata added.  summary_documents — new Document instances for
        document-level and topic-cluster summaries.
    """
    tagged = tag_documents_with_topics(documents)

    summaries: list[Document] = []

    # Document-level summaries (from full text when available)
    if doc_texts:
        seen_ids: set[str] = set()
        for full_text, meta in doc_texts:
            doc_id = meta.get("doc_id", "")
            if not doc_id or doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            summary = generate_document_summary(
                doc_id,
                full_text,
                meta,
                max_sentences=max_doc_summary_sentences,
                min_text_length=min_doc_text_length,
            )
            if summary:
                summaries.append(summary)

        # Tag document summaries with topics based on their content
        if summaries:
            doc_summaries = [
                s for s in summaries if s.metadata.get("doc_type") == "document_summary"
            ]
            if doc_summaries:
                tagged_doc_summaries = tag_documents_with_topics(doc_summaries)
                # Replace untagged document summaries with tagged ones
                summaries = [
                    s for s in summaries if s.metadata.get("doc_type") != "document_summary"
                ]
                summaries.extend(tagged_doc_summaries)

    # Topic-cluster summaries
    clusters = cluster_documents(tagged)
    for topic_name, cluster_docs in clusters.items():
        topic_summary = generate_topic_summary(
            topic_name,
            cluster_docs,
            max_sentences=max_topic_summary_sentences,
            min_chunks=min_topic_chunks,
        )
        if topic_summary:
            summaries.append(topic_summary)

    logger.info(
        "Generated %d summaries (%d document-level, %d topic-cluster)",
        len(summaries),
        sum(1 for s in summaries if s.metadata.get("doc_type") == "document_summary"),
        sum(1 for s in summaries if s.metadata.get("doc_type") == "topic_summary"),
    )

    return tagged, summaries
