# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- **HCPCS/ICD-10-CM semantic enrichment** (`src/medicare_rag/ingest/enrich.py`): New module
  that prepends category labels, synonyms, and related terms to code document text before
  embedding. This bridges the semantic gap between terse code descriptions (e.g.,
  "Cane, includes canes of all materials, adjustable or fixed, with tip") and natural-language
  queries (e.g., "What HCPCS codes are used for durable medical equipment?").

  - **HCPCS Level II** mappings cover all letter prefixes (A through V) with sub-range
    granularity. For example, E0-E8 codes are tagged with "Durable Medical Equipment" and
    related terms like "wheelchair", "hospital bed", "oxygen equipment", "CPAP", "walker".
  - **ICD-10-CM** mappings cover all 22 chapter ranges (A00-B99 through Z00-Z99). For example,
    I00-I99 codes are tagged with "Diseases of the Circulatory System" and related terms like
    "hypertension", "heart failure", "stroke", "atrial fibrillation".
  - Enrichment is applied automatically during extraction — no extra pipeline step required.
  - Unknown or unrecognised code prefixes pass through unchanged.

- **Enrichment unit tests** (`tests/test_enrich.py`): 38 tests covering HCPCS enrichment
  (15 code prefix tests), ICD-10-CM enrichment (17 chapter range tests), edge cases (empty/numeric
  codes, unknown prefixes), and the `enrich_*_text` wrapper functions.

- **Baseline eval artifacts**: Previous eval metrics and report preserved as
  `scripts/eval_metrics_baseline.json` and `scripts/eval_report_baseline.md` for comparison.

### Changed

- **`extract.py`**: HCPCS record writer (`_write_hcpcs_record`) and ICD-10-CM extractor
  (`extract_icd10cm`) now call `enrich_hcpcs_text()` / `enrich_icd10_text()` to prepend
  semantic enrichment before writing documents to disk.

- **`test_ingest.py`**: Updated `test_extract_hcpcs_writes_txt_and_meta` and
  `test_extract_icd10cm_writes_txt_and_meta` to verify enrichment text appears in output.

### Eval Results — Code Lookup Improvements

Evaluation run on 2026-02-18 using the same 63-question eval set (k=5).

**code_lookup category (primary target):**

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Hit rate | 14% (1/7) | 57% (4/7) | **+43pp** |
| MRR | 0.143 | 0.500 | **+0.357** |
| Precision@5 | 0.086 | 0.486 | **+0.400** |

Three HCPCS queries that previously failed now pass at rank 1 with perfect precision:

| Query | Before | After |
|-------|--------|-------|
| "HCPCS Level II codes for supplies and procedures" | FAIL | **PASS (rank 1, P@5=1.0)** |
| "What HCPCS codes are used for durable medical equipment?" | FAIL | **PASS (rank 1, P@5=1.0)** |
| "HCPCS J codes for injectable drugs administered in physician office" | FAIL | **PASS (rank 1, P@5=1.0)** |

**cross_source category (also improved):**

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| MRR | 0.675 | 1.000 | **+0.325** |
| Precision@5 | 0.700 | 0.950 | **+0.250** |

Notable: "Durable medical equipment coverage policy and HCPCS codes" improved from rank 5
(P@5=0.20) to rank 1 (P@5=0.80).

**codes expected source (overall):**

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Hit rate | 67% | 72% | **+5pp** |
| MRR | 0.567 | 0.667 | **+0.100** |

**Consistency improved:** Average Jaccard 0.483 → 0.733 (+0.250).

ICD-10-CM specific queries remain unresolved (requires `ICD10_CM_ZIP_URL` for data download).
