"""Topic clustering for fragmented Medicare content.

Groups chunks by clinical/policy topic so that related content scattered
across IOM chapters, MCD LCDs, and code documents can be consolidated
into topic-level summaries.  This improves retrieval stability when users
rephrase the same question in different ways.

Each topic is defined by a set of keyword patterns.  A chunk may belong
to multiple topics (e.g. "cardiac rehab billing codes" touches both the
cardiac_rehab and billing topics).

Topic definitions are loaded from DATA_DIR/topic_definitions.json when
present; otherwise the package default (medicare_rag/data/topic_definitions.json)
is used.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from langchain_core.documents import Document

from medicare_rag.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TopicDef:
    """Immutable definition of a Medicare topic cluster."""

    name: str
    label: str
    patterns: tuple[re.Pattern[str], ...]
    summary_prefix: str = ""
    min_pattern_matches: int = 1


def _compile(raw: list[str]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(p, re.IGNORECASE) for p in raw)


def _load_topic_definitions() -> list[TopicDef]:
    """Load topic definitions from DATA_DIR/topic_definitions.json or package default."""
    path = DATA_DIR / "topic_definitions.json"
    if path.exists():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read %s: %s; using package default", path, e)
            raw = None
    else:
        raw = None

    if raw is None:
        from importlib.resources import files

        pkg_path = files("medicare_rag") / "data" / "topic_definitions.json"
        try:
            raw = pkg_path.read_text(encoding="utf-8")
        except Exception as e:
            raise FileNotFoundError(
                f"Topic definitions not found at {path} or package default: {e}"
            ) from e

    data = json.loads(raw)
    out: list[TopicDef] = []
    for item in data:
        name = item.get("name", "")
        label = item.get("label", name)
        patterns_raw = item.get("patterns") or []
        summary_prefix = item.get("summary_prefix", "")
        min_pattern_matches = max(1, int(item.get("min_pattern_matches", 1)))
        out.append(
            TopicDef(
                name=name,
                label=label,
                patterns=_compile(patterns_raw),
                summary_prefix=summary_prefix,
                min_pattern_matches=min_pattern_matches,
            )
        )
    return out


TOPIC_DEFINITIONS: list[TopicDef] = _load_topic_definitions()
_TOPIC_DEF_MAP: dict[str, TopicDef] = {td.name: td for td in TOPIC_DEFINITIONS}


def assign_topics(doc: Document) -> list[str]:
    """Return the list of topic names that match the document content."""
    text = doc.page_content
    topics: list[str] = []
    for topic_def in TOPIC_DEFINITIONS:
        matches = sum(1 for p in topic_def.patterns if p.search(text))
        if matches >= topic_def.min_pattern_matches:
            topics.append(topic_def.name)
    return topics


def cluster_documents(documents: list[Document]) -> dict[str, list[Document]]:
    """Group documents by topic cluster.

    Returns a mapping from topic name to the list of documents that
    belong to that cluster.  Documents may appear in multiple clusters.
    """
    clusters: dict[str, list[Document]] = {}
    for doc in documents:
        topics = assign_topics(doc)
        for topic in topics:
            clusters.setdefault(topic, []).append(doc)
    return clusters


def get_topic_def(name: str) -> TopicDef | None:
    """Look up a topic definition by name."""
    return _TOPIC_DEF_MAP.get(name)


def tag_documents_with_topics(documents: list[Document]) -> list[Document]:
    """Add ``topic_clusters`` metadata to each document.

    Returns new Document instances (original list is not mutated).
    """
    tagged: list[Document] = []
    for doc in documents:
        topics = assign_topics(doc)
        if topics:
            meta = dict(doc.metadata)
            meta["topic_clusters"] = ",".join(topics)
            tagged.append(Document(page_content=doc.page_content, metadata=meta))
        else:
            tagged.append(doc)
    return tagged
