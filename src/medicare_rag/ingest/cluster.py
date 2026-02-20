"""Topic clustering for fragmented Medicare content.

Groups chunks by clinical/policy topic so that related content scattered
across IOM chapters, MCD LCDs, and code documents can be consolidated
into topic-level summaries.  This improves retrieval stability when users
rephrase the same question in different ways.

Each topic is defined by a set of keyword patterns.  A chunk may belong
to multiple topics (e.g. "cardiac rehab billing codes" touches both the
cardiac_rehab and billing topics).
"""

import re
from dataclasses import dataclass

from langchain_core.documents import Document


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


TOPIC_DEFINITIONS: list[TopicDef] = [
    TopicDef(
        name="cardiac_rehab",
        label="Cardiac Rehabilitation",
        patterns=_compile([
            r"\bcardiac\s*rehab",
            r"\bcardiac\s+rehabilitation\b",
            r"\bheart\s+rehabilitation\b",
            r"\bcardiovascular\s+rehab",
            r"\bintensive\s+cardiac\s+rehab",
            r"\bICR\b",
            r"\bcardiac\s+recovery\b",
            r"\bcardiac\s+exercise\b",
        ]),
        summary_prefix="Cardiac Rehabilitation: ",
    ),
    TopicDef(
        name="wound_care",
        label="Wound Care and Management",
        patterns=_compile([
            r"\bwound\s*care\b",
            r"\bwound\s+management\b",
            r"\bwound\s*vac\b",
            r"\bnegative\s+pressure\s+wound\b",
            r"\bNPWT\b",
            r"\bdebridement\b",
            r"\bpressure\s+ulcer\b",
            r"\bdecubitus\b",
            r"\bchronic\s+wound\b",
            r"\bskin\s+graft\b",
            r"\bwound\s+healing\b",
        ]),
        summary_prefix="Wound Care: ",
    ),
    TopicDef(
        name="hyperbaric_oxygen",
        label="Hyperbaric Oxygen Therapy",
        patterns=_compile([
            r"\bhyperbaric\s+oxygen\b",
            r"\bHBOT\b",
            r"\bhyperbaric\s+therapy\b",
            r"\bhyperbaric\s+chamber\b",
            r"\btopical\s+oxygen\b",
        ]),
        summary_prefix="Hyperbaric Oxygen Therapy: ",
    ),
    TopicDef(
        name="dme",
        label="Durable Medical Equipment",
        patterns=_compile([
            r"\bdurable\s+medical\s+equipment\b",
            r"\bDME\b",
            r"\bwheelchair\b",
            r"\bhospital\s+bed\b",
            r"\boxygen\s+equipment\b",
            r"\bCPAP\b",
            r"\bBiPAP\b",
            r"\bnebulizer\b",
            r"\bwalker\b",
        ]),
        summary_prefix="Durable Medical Equipment: ",
    ),
    TopicDef(
        name="physical_therapy",
        label="Physical Therapy and Rehabilitation",
        patterns=_compile([
            r"\bphysical\s+therapy\b",
            r"\boutpatient\s+rehabilitation\b",
            r"\bPT\s+services?\b",
            r"\bphysical\s+therapist\b",
            r"\brehabilitation\s+services?\b",
            r"\boccupational\s+therapy\b",
            r"\bOT\s+services?\b",
        ]),
        summary_prefix="Physical Therapy: ",
    ),
    TopicDef(
        name="imaging",
        label="Diagnostic Imaging",
        patterns=_compile([
            r"\bdiagnostic\s+imaging\b",
            r"\bMRI\b",
            r"\bCT\s+scan\b",
            r"\bX[- ]?ray\b",
            r"\bultrasound\b",
            r"\bPET\s+scan\b",
            r"\bmammograph",
            r"\badvanced\s+imaging\b",
            r"\bradiology\b",
        ]),
        summary_prefix="Diagnostic Imaging: ",
    ),
    TopicDef(
        name="home_health",
        label="Home Health Services",
        patterns=_compile([
            r"\bhome\s+health\b",
            r"\bHHA\b",
            r"\bhome\s+health\s+agency\b",
            r"\bskilled\s+nursing\b",
            r"\bhomebound\b",
            r"\bhome\s+care\b",
        ]),
        summary_prefix="Home Health: ",
    ),
    TopicDef(
        name="hospice",
        label="Hospice and Palliative Care",
        patterns=_compile([
            r"\bhospice\b",
            r"\bpalliative\s+care\b",
            r"\bend[- ]of[- ]life\b",
            r"\bterminal\s+(?:illness|care|prognosis)\b",
        ]),
        summary_prefix="Hospice Care: ",
    ),
    TopicDef(
        name="dialysis",
        label="Dialysis and ESRD",
        patterns=_compile([
            r"\bdialysis\b",
            r"\bESRD\b",
            r"\bend[- ]stage\s+renal\b",
            r"\bhemodialysis\b",
            r"\bperitoneal\s+dialysis\b",
            r"\bkidney\s+disease\b",
        ]),
        summary_prefix="Dialysis/ESRD: ",
    ),
    TopicDef(
        name="chemotherapy",
        label="Chemotherapy and Oncology",
        patterns=_compile([
            r"\bchemotherapy\b",
            r"\boncology\b",
            r"\bantineoplastic\b",
            r"\bcancer\s+treatment\b",
            r"\bimmunotherapy\b",
            r"\bradiation\s+therapy\b",
        ]),
        summary_prefix="Chemotherapy/Oncology: ",
    ),
    TopicDef(
        name="mental_health",
        label="Mental and Behavioral Health",
        patterns=_compile([
            r"\bmental\s+health\b",
            r"\bbehavioral\s+health\b",
            r"\bpsychiatr",
            r"\bpsycholog",
            r"\bsubstance\s+(?:abuse|use)\b",
            r"\bdepression\b",
            r"\banxiety\b",
        ]),
        summary_prefix="Mental Health: ",
    ),
    TopicDef(
        name="ambulance",
        label="Ambulance and Transport Services",
        patterns=_compile([
            r"\bambulance\b",
            r"\bemergency\s+(?:medical\s+)?transport\b",
            r"\bnon[- ]emergency\s+transport\b",
            r"\bBLS\s+(?:transport|ambulance|unit|crew|level)\b",
            r"\bALS\s+(?:transport|ambulance|unit|crew|level|intercept)\b",
            r"\bparamedic\b",
        ]),
        summary_prefix="Ambulance Services: ",
    ),
    TopicDef(
        name="infusion_therapy",
        label="Infusion Therapy",
        patterns=_compile([
            r"\binfusion\s+therapy\b",
            r"\bIV\s+(?:infusion|therapy|drug)\b",
            r"\binjectable\s+drug\b",
            r"\bdrug\s+administration\b",
            r"\binfusion\s+pump\b",
        ]),
        summary_prefix="Infusion Therapy: ",
    ),
]

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
