# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added

- **LCD-aware retriever** (`src/medicare_rag/query/retriever.py`): Complete rewrite of the
  retriever with an `LCDAwareRetriever` class that detects LCD/coverage-determination queries
  and applies multi-query retrieval to dramatically improve hit rates on MCD policy content.

  - **Query detection** (`is_lcd_query`): Regex-based classification recognises LCD/NCD/MCD
    terms, MAC contractor names (Novitas, Palmetto, First Coast, etc.), jurisdiction codes
    (JA–JL), and coverage-plus-therapy patterns (e.g., "hyperbaric oxygen therapy covered").
  - **Query expansion** (`expand_lcd_query`): Produces up to three query variants —
    (1) original, (2) topic-expanded with clinical synonyms, and (3) a concept-stripped
    version that removes contractor names and LCD jargon so the embedding focuses on the
    clinical topic.
  - **Round-robin interleaving** (`_deduplicate_docs`): Merges results from all query
    variants via round-robin rather than concatenation, ensuring each variant contributes
    documents near the top of the result list instead of one variant dominating all slots.
  - **Source-filtered MCD retrieval**: Expanded queries run through a `source=mcd` filter
    to guarantee coverage-determination documents appear in results.
  - Non-LCD queries continue to use standard single-query similarity search.

- **LCD-specific chunking parameters** (`config.py`, `chunk.py`):
  - `LCD_CHUNK_SIZE` (default 1500, env-overridable) — 50 % larger than the standard
    `CHUNK_SIZE` (1000) to preserve more LCD policy context per chunk.
  - `LCD_CHUNK_OVERLAP` (default 300, env-overridable) — proportionally larger overlap
    to maintain continuity between LCD chunks.
  - `LCD_RETRIEVAL_K` (default 12, env-overridable) — higher k for LCD queries.
  - MCD source documents are automatically chunked with the LCD-specific parameters;
    IOM and code documents remain on the standard settings.

- **LCD retrieval tests** (`tests/test_query.py`): 46 new tests covering `is_lcd_query`
  detection (15 cases), `expand_lcd_query` expansion (8 cases), `_strip_to_medical_concept`
  (4 cases), `_deduplicate_docs` round-robin merge (6 cases), `LCDAwareRetriever` with
  mocked store (6 cases), and MCD chunk sizing (3 cases in `test_ingest.py`), plus LCD
  config defaults (4 cases in `test_config.py`).

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

### Eval Results — LCD Policy Retrieval Improvements

Evaluation run on 2026-02-19 against the `lcd_policy` category (6 questions, k=8)
after downloading and indexing the full MCD bulk data (33,805 chunks).

**lcd_policy category hit rate: 33 % → 100 %**

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Hit rate | 33 % (2/6) | 100 % (6/6) | **+67 pp** |
| MRR | 0.333 | 0.722 | **+0.389** |
| Avg NDCG@8 | — | 0.959 | — |

Per-question results:

| Query | Before | After |
|-------|--------|-------|
| "Does Novitas (JL) have an LCD for cardiac rehab?" | FAIL | **PASS (rank 3)** |
| "Is hyperbaric oxygen therapy covered for diabetic wounds?" | FAIL | **PASS (rank 2, P@8=0.25)** |
| "What are the national coverage determination criteria…?" | PASS | **PASS (rank 1, P@8=0.75)** |
| "What LCDs apply to outpatient physical therapy services?" | FAIL | **PASS (rank 2, P@8=0.50)** |
| "LCD coverage for advanced imaging MRI and CT scans" | FAIL | **PASS (rank 1, P@8=0.50)** |
| "Medicare coverage for wound care and wound vac therapy" | PASS | **PASS (rank 1, P@8=1.00)** |

Key techniques that achieved this:

1. **Larger MCD chunks** (1500 vs 1000 chars) preserve LCD policy text context.
2. **LCD query detection** via regex for LCD terms, contractor names, and
   therapy-plus-coverage patterns.
3. **Multi-query retrieval** with three variants: original, topic-expanded, and
   concept-stripped (contractor/LCD jargon removed).
4. **Round-robin interleaving** across variants ensures each contributes docs near
   the top of results.
5. **MCD source-filtered search** guarantees coverage-determination documents appear.

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
