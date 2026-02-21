---
description: "Semantic enrichment: prepending category labels and related terms to HCPCS and ICD-10 documents to improve embedding alignment with natural-language queries."
---

# Semantic Enrichment Pipeline

The semantic enrichment module (`src/medicare_rag/ingest/enrich.py`) addresses a core challenge in medical code retrieval: users ask questions in natural language ("What wheelchair does Medicare cover?") but the underlying documents use alphanumeric codes (E0100). Enrichment bridges this gap by prepending semantic context to code documents before embedding.

## How It Works

- **HCPCS enrichment** — maps the code's leading letter and two-character prefix to a category label and list of related terms. For example, code E0100 gets: "HCPCS E-codes: Durable Medical Equipment. Related terms: wheelchair, hospital bed, oxygen equipment, CPAP, walker..." This text is prepended to the code's description.
- **ICD-10-CM enrichment** — maps the code to its ICD-10-CM chapter and prepends the chapter label and related terms. For example, code I25.10 gets: "ICD-10-CM (I00-I99): Diseases of the Circulatory System. Related terms: cardiovascular disease, heart disease, hypertension..."

## Why It Matters

Without enrichment, the embedding for "E0100 — wheelchair, motorized, with programmer" would be distant from the query embedding for "durable medical equipment coverage." With enrichment, the document contains the terms "durable medical equipment," "DME," and "wheelchair" in its preamble, pulling the embedding vector closer to natural-language queries.

## Implementation

- Sub-range matching: HCPCS codes are matched against ordered sub-ranges (e.g., A0 for ambulance, A4-A8 for supplies) with letter-level fallbacks
- Chapter matching: ICD-10-CM codes are matched against chapter ranges (A00-B99, C00-D49, etc.) with special handling for ranges with letter suffixes (e.g., O9A)
- Pure lookup — no external API calls, no ML models; enrichment is deterministic and fast

## Connections

Enrichment is applied during the [[extraction-pipeline]] before [[chunking-strategy]]. It improves retrieval quality in the [[vector-store]], which is validated by the [[eval-framework]]. The enrichment data structures define the semantic vocabulary that maps [[hcpcs-level-ii]] and [[icd-10-cm]] to natural-language concepts used in [[billing-and-coding]] and [[coverage-determination]].
