"""Cross-source query expansion for Medicare RAG retrieval.

Detects which source types (IOM, MCD, codes) are relevant to a query and
generates additional query variants that target each source's vocabulary,
improving recall for questions that span multiple sources.
"""

import re

_IOM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bpart\s+[a-d]\b",
        r"\biom\b",
        r"\binternet\s+only\s+manual\b",
        r"\bcms\s+manual\b",
        r"\bclaim(?:s)?\s*(?:processing|submission|filing)\b",
        r"\bbenefit(?:s)?\s*(?:policy|period)\b",
        r"\benrollment\b",
        r"\beligibility\b",
        r"\bmedicare\b.*\b(?:policy|guideline|manual|chapter|rule)\b",
        r"\bgeneral\s+billing\b",
        r"\bmsn\b",
        r"\bmedicare\s+summary\s+notice\b",
        r"\bappeal(?:s)?\b",
        r"\bredetermination\b",
    ]
]

_MCD_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\blcds?\b",
        r"\bncds?\b",
        r"\bcoverage\s+determination\b",
        r"\bmedical\s+necessity\b",
        r"\bcoverage\s+criteria\b",
        r"\bindication(?:s)?\b",
        r"\blimitation(?:s)?\b",
        r"\bcontractor\b",
        r"\bjurisdiction\b",
        r"\bmcd\b",
        r"\bnovitas\b",
        r"\bfirst\s+coast\b",
        r"\bpalmetto\b",
        r"\bnoridian\b",
        r"\bcovered?\b.{0,30}\bservice",
    ]
]

_CODES_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bhcpcs\b",
        r"\bcpt\b",
        r"\bicd[- ]?10\b",
        r"\bprocedure\s+code\b",
        r"\bdiagnosis\s+code\b",
        r"\bbilling\s+code\b",
        r"\bcode(?:s)?\s+for\b",
        r"\bmodifier\b",
        r"\bdrg\b",
        r"\brevenue\s+code\b",
        r"\b[A-Z]\d{4}\b",
    ]
]

_SOURCE_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "iom": _IOM_PATTERNS,
    "mcd": _MCD_PATTERNS,
    "codes": _CODES_PATTERNS,
}

# Per-source expansion suffixes keyed by source type
_SOURCE_EXPANSIONS: dict[str, str] = {
    "iom": "Medicare policy guidelines manual chapter benefit rules",
    "mcd": "coverage determination LCD NCD criteria medical necessity indications limitations",
    "codes": "HCPCS CPT ICD-10 procedure diagnosis billing codes",
}

# Medicare domain synonyms: maps common terms to related terms that
# may appear in different source types
_SYNONYM_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(p, re.IGNORECASE), expansion)
    for p, expansion in [
        (r"\bcoverage\b", "covered services benefits policy"),
        (r"\bbilling\b", "claims reimbursement payment"),
        (r"\brehabilitation\b", "rehab therapy treatment program"),
        (r"\bwound\s*care\b", "wound management debridement negative pressure therapy"),
        (r"\bimaging\b", "diagnostic imaging MRI CT scan X-ray ultrasound"),
        (r"\bdurable\s+medical\s+equipment\b", "DME prosthetic orthotic supplies"),
        (r"\bhome\s+health\b", "home health agency HHA skilled nursing"),
        (r"\bhospice\b", "hospice palliative end-of-life terminal care"),
        (r"\bambulance\b", "ambulance transport emergency non-emergency"),
        (r"\binfusion\b", "infusion injection drug administration"),
        (r"\bphysical\s+therapy\b", "physical therapy PT outpatient rehabilitation"),
        (r"\boccupational\s+therapy\b", "occupational therapy OT rehabilitation"),
        (r"\bspeech\s+therapy\b", "speech-language pathology SLP therapy"),
        (r"\bmental\s+health\b", "behavioral health psychiatric psychological services"),
        (r"\bdialysis\b", "dialysis ESRD end-stage renal disease"),
        (r"\bchemotherapy\b", "chemotherapy oncology cancer treatment"),
    ]
]


def detect_source_relevance(query: str) -> dict[str, float]:
    """Score each source type's relevance to the query on a 0.0–1.0 scale.

    When no specific source signals are detected, returns moderate scores
    for all sources so cross-source retrieval still casts a wide net.
    """
    scores: dict[str, float] = {}
    for name, patterns in _SOURCE_PATTERNS.items():
        threshold = max(1, len(patterns) // 3)
        matches = sum(1 for p in patterns if p.search(query))
        scores[name] = min(1.0, matches / threshold)

    if all(v == 0 for v in scores.values()):
        return {"iom": 0.4, "mcd": 0.3, "codes": 0.3}
    return scores


def _apply_synonyms(query: str) -> str:
    """Expand a query with Medicare domain synonyms."""
    additions: list[str] = []
    for pattern, expansion in _SYNONYM_MAP:
        if pattern.search(query):
            additions.append(expansion)
    if not additions:
        return query
    return f"{query} {' '.join(additions)}"


def expand_cross_source_query(query: str) -> list[str]:
    """Expand a query into multiple variants optimized for different sources.

    Returns a list where the first element is always the original query,
    followed by source-specific variants for each relevant source, and
    optionally a synonym-expanded variant.
    """
    variants = [query]
    relevance = detect_source_relevance(query)

    for source, score in relevance.items():
        if score > 0:
            expansion = _SOURCE_EXPANSIONS[source]
            variants.append(f"{query} {expansion}")

    synonym_expanded = _apply_synonyms(query)
    if synonym_expanded != query:
        variants.append(synonym_expanded)

    return variants
