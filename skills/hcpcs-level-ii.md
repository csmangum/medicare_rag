---
description: "HCPCS Level II codes (A0000–V5999): alphanumeric codes for supplies, DME, drugs, ambulance services, and other items not covered by CPT. Maintained by CMS."
---

# HCPCS Level II

The Healthcare Common Procedure Coding System Level II is the code set maintained by CMS for services, supplies, and equipment not described by CPT codes. HCPCS Level II codes are alphanumeric (one letter followed by four digits) and organized by the leading letter into broad categories.

## Code Categories

The first character determines the domain. The RAG system's [[semantic-enrichment-pipeline]] uses these prefixes to inject category context into embeddings:

- **A-codes** — transportation/ambulance (A0), medical and surgical supplies (A1–A8), administrative (A9)
- **B-codes** — enteral and parenteral therapy
- **C-codes** — outpatient PPS and temporary hospital codes
- **D-codes** — dental procedures
- **E-codes** — durable medical equipment (wheelchairs, hospital beds, oxygen, CPAP)
- **G-codes** — temporary procedures and professional services (telehealth, screenings, quality measures)
- **J-codes** — drugs administered other than oral method (J0–J8: injectables; J9: chemotherapy)
- **K-codes** — temporary DME codes
- **L-codes** — orthotics (L0–L4) and prosthetics (L5–L9)
- **Q-codes** — temporary codes (cast supplies, hospice, skin substitutes)
- **V-codes** — vision (V0–V2) and hearing/speech (V5) services

## Fixed-Width File Format

CMS distributes HCPCS data as a fixed-width text file (320 characters per record). The RAG system's extractor parses field positions for code, long description, short description, effective date, and Record Identification Code (RIC). RIC values distinguish primary records (3=procedure, 7=modifier) from continuation records (4, 8) that extend the long description.

## Connections

HCPCS codes appear on claims processed through the [[claims-lifecycle]] and are evaluated against [[local-coverage-determinations]] and [[national-coverage-determinations]]. They pair with [[icd-10-cm]] diagnosis codes to establish [[medical-necessity-coding]]. The code's prefix determines [[modifiers]] applicability and fee schedule assignment. HCPCS data is enriched by [[semantic-enrichment-pipeline]] and indexed in the [[vector-store]].
