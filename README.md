# Medicare RAG

A **Retrieval-Augmented Generation (RAG)** proof-of-concept for Medicare Revenue Cycle Management. It ingests CMS manuals, coverage determinations, and coding files; embeds them in a vector store; and answers natural-language questions with cited sources. Everything runs locally—no API keys required.

## What it does

- **Download** — IOM manuals (100-02, 100-03, 100-04), MCD bulk data, HCPCS and optional ICD-10-CM code files into `data/raw/`.
- **Ingest** — Extract text (PDF and structured sources), enrich HCPCS/ICD-10 documents with semantic labels and related terms, chunk with LangChain splitters, embed with sentence-transformers, and upsert into ChromaDB with incremental updates by content hash.
- **Query** — Interactive REPL and RAG chain: retrieve relevant chunks, then generate answers using a local Hugging Face model (e.g. TinyLlama) with citations.
- **Validate & evaluate** — Index validation (metadata, sources, embedding dimension) and retrieval evaluation (hit rate, MRR) against a Medicare-focused question set.
- **Embedding search UI** — Optional Streamlit app for interactive semantic search over the index with filters and quick-check questions.

## Requirements

- **Python 3.11+**
- **No API keys** — Embeddings and LLM run locally via sentence-transformers and Hugging Face.

## Quick start

```bash
# Create venv and install
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .

# Optional: copy .env.example to .env for paths and model overrides
cp .env.example .env

# Download data (IOM, MCD, codes)
python scripts/download_all.py --source all

# Extract, chunk, embed, and store
python scripts/ingest_all.py --source all

# Ask questions (RAG with local LLM)
python scripts/query.py
```

## Pipeline in detail

### 1. Download

```bash
python scripts/download_all.py [--source iom|mcd|codes|all] [--force]
```

- **Sources:** `iom` (IOM manuals), `mcd` (MCD bulk ZIP), `codes` (HCPCS + optional ICD-10-CM), or `all`.
- **Idempotent:** Skips when manifest and files exist; use `--force` to re-download.
- Output: `data/raw/<source>/` plus a `manifest.json` per source (URL, date, file list, optional SHA-256). Set `ICD10_CM_ZIP_URL` in `.env` if you want ICD-10-CM (see [CDC](https://www.cdc.gov/nchs/icd/icd-10-cm.htm)).

### 2. Ingest (extract → chunk → embed → store)

```bash
python scripts/ingest_all.py [--source iom|mcd|codes|all] [--force] [--skip-index]
```

- **Extract:** PDFs (pdfplumber; optional `unstructured` for image-heavy PDFs), MCD/codes from structured files. HCPCS and ICD-10-CM documents are automatically enriched with category labels, synonyms, and related terms (e.g., E-codes get "Durable Medical Equipment: wheelchair, hospital bed, oxygen equipment...") to improve semantic retrieval.
- **Chunk:** LangChain text splitters; metadata (source, manual, jurisdiction, etc.) is preserved.
- **Embed & store:** sentence-transformers (default `all-MiniLM-L6-v2`) and ChromaDB at `data/chroma/` (collection `medicare_rag`). Only new or changed chunks (by content hash) are re-embedded and upserted.
- Use `--skip-index` to run only extract and chunk (no embedding or vector store).

### 3. Query (RAG)

```bash
python scripts/query.py [--filter-source iom|mcd|codes] [--filter-manual 100-02] [--filter-jurisdiction JL] [-k 8]
```

- Retrieves top-k chunks by similarity, then generates an answer with the local LLM and prints cited sources.
- **Env:** `LOCAL_LLM_MODEL`, `LOCAL_LLM_DEVICE` (e.g. `cpu` or `auto`), `LOCAL_LLM_MAX_NEW_TOKENS`, `LOCAL_LLM_REPETITION_PENALTY`. Use `CUDA_VISIBLE_DEVICES=""` for CPU-only.

### 4. Validate and evaluate

```bash
python scripts/validate_and_eval.py                    # validate index + run retrieval eval
python scripts/validate_and_eval.py --validate-only    # index only
python scripts/validate_and_eval.py --eval-only -k 10  # retrieval eval only
python scripts/validate_and_eval.py --eval-only --json  # metrics as JSON
```

- **Validation:** Checks Chroma collection, document count, sample metadata (`doc_id`, `content_hash`), and that similarity search runs.
- **Evaluation:** Uses `scripts/eval_questions.json` (Medicare queries with expected keywords/sources). Reports **hit rate** (relevant doc in top-k) and **MRR** (mean reciprocal rank). Edit `eval_questions.json` to extend the set. Output from `validate_and_eval.py --json` may be saved as `scripts/eval_metrics.json` and committed as a snapshot of the last run.

**Full-RAG eval (answer quality):** Run the RAG chain on the eval set and write a report for manual review:

```bash
python scripts/run_rag_eval.py [--eval-file scripts/eval_questions.json] [--out data/rag_eval_report.md] [-k 8]
```

### 5. Embedding search UI (optional)

```bash
pip install -e ".[ui]"
streamlit run app.py
```

- Semantic search over the index with a search bar and quick-check question buttons.
- Filters: source, manual, jurisdiction.
- Options: top-k, distance threshold, full chunk content.
- Styled result cards with similarity scores and metadata.

## Evaluation Findings

Full pipeline evaluation run on 2026-02-18 using default settings (embedding model: `all-MiniLM-L6-v2`, LLM: `TinyLlama-1.1B-Chat-v1.0`, chunk size: 1000, overlap: 200, k=5) with HCPCS/ICD-10 semantic enrichment enabled. Data sources: IOM manuals 100-02/03/04, MCD bulk data, and HCPCS codes (ICD-10-CM not included — requires `ICD10_CM_ZIP_URL`).

### Index Summary

| Metric | Value |
|--------|-------|
| Total documents (chunks) | 36,090 |
| IOM chunks | 17,238 (47.8%) |
| MCD chunks | 9,847 (27.3%) |
| Codes chunks | 9,005 (24.9%) |
| Embedding dimension | 384 |
| Content length (median) | 467 chars |
| Content length (p5–p95) | 83–989 chars |
| Validation checks | 23/23 passed |
| Duplicate IDs | 0 |
| Empty documents | 0 |

### Semantic Enrichment Impact

The biggest change from the previous baseline is the addition of semantic enrichment for HCPCS/ICD-10 code documents. Each code document is now prepended with category labels and related terms before embedding. For example, HCPCS code E0100 ("Cane, adjustable or fixed") now includes:

> *HCPCS E-codes: Durable Medical Equipment. Related terms: durable medical equipment, DME, wheelchair, hospital bed, oxygen equipment, CPAP, BiPAP, walker, cane, crutch...*

This provides the semantic bridge that allows natural-language queries like "What HCPCS codes are used for durable medical equipment?" to match code documents that would otherwise only contain terse clinical descriptions.

#### Code Lookup — Before and After Enrichment

| Metric | Before (baseline) | After (enriched) | Delta |
|--------|--------------------|-------------------|-------|
| Hit rate | 14% (1/7) | **57% (4/7)** | **+43pp** |
| MRR | 0.143 | **0.500** | **+0.357** |
| Precision@5 | 0.086 | **0.486** | **+0.400** |

| Query | Before | After |
|-------|--------|-------|
| "HCPCS Level II codes for supplies and procedures" | FAIL | **PASS (rank 1, P@5=1.0)** |
| "What HCPCS codes are used for durable medical equipment?" | FAIL | **PASS (rank 1, P@5=1.0)** |
| "HCPCS J codes for injectable drugs" | FAIL | **PASS (rank 1, P@5=1.0)** |
| "ICD-10-CM codes for COPD" | PASS (rank 1) | PASS (rank 2) |
| ICD-10 hypertension / chest pain / diabetes | FAIL | FAIL (no data) |

#### Cross-Source — Before and After Enrichment

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| MRR | 0.675 | **1.000** | **+0.325** |
| P@5 | 0.700 | **0.950** | **+0.250** |

"Durable medical equipment coverage policy and HCPCS codes" improved from rank 5 (P@5=0.20) to **rank 1 (P@5=0.80)**. "Medicare billing rules and codes for laboratory tests" improved from rank 2 (P@5=0.60) to **rank 1 (P@5=1.00)**.

#### Codes Expected Source — Before and After

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Hit rate | 67% | **72%** | +5pp |
| MRR | 0.567 | **0.667** | +0.100 |

#### Consistency — Improved

| Group | Before | After | Delta |
|-------|--------|-------|-------|
| cardiac_rehab | 0.167 | **0.667** | +0.500 |
| wheelchair | 0.800 | 0.800 | 0.000 |
| **Average** | 0.483 | **0.733** | **+0.250** |

### Retrieval Evaluation (63 questions, k=5)

| Metric | Value |
|--------|-------|
| **Hit Rate** | **73.0%** (46/63) |
| **MRR** | **0.6090** |
| **Avg Precision@5** | **0.5175** |
| **Avg NDCG@5** | **0.9229** |
| Median latency | 6 ms |
| p95 latency | 8 ms |

#### Performance by category

| Category | n | Hit Rate | MRR | P@k | NDCG@k |
|----------|---|----------|-----|-----|--------|
| claims_billing | 6 | 100% | 1.000 | 0.933 | 0.979 |
| cross_source | 4 | 100% | 1.000 | 0.950 | 0.987 |
| payment | 3 | 100% | 1.000 | 0.867 | 0.982 |
| consistency | 4 | 100% | 0.667 | 0.500 | 0.964 |
| compliance | 3 | 100% | 0.556 | 0.400 | 0.915 |
| coding_modifiers | 5 | 80% | 0.800 | 0.600 | 0.981 |
| edge_case | 4 | 75% | 0.500 | 0.450 | 0.971 |
| policy_coverage | 6 | 67% | 0.500 | 0.433 | 0.974 |
| semantic_retrieval | 5 | 60% | 0.500 | 0.320 | 0.975 |
| abbreviation | 5 | 60% | 0.340 | 0.280 | 0.950 |
| appeals_denials | 5 | 60% | 0.467 | 0.400 | 0.943 |
| **code_lookup** | **7** | **57%** | **0.500** | **0.486** | **0.680** |
| lcd_policy | 6 | 33% | 0.333 | 0.267 | 0.839 |

#### Performance by expected source

| Source | n | Hit Rate | MRR | P@k | NDCG@k |
|--------|---|----------|-----|-----|--------|
| iom | 52 | 81% | 0.671 | 0.562 | 0.967 |
| codes | 18 | 72% | 0.667 | 0.578 | 0.860 |
| mcd | 16 | 69% | 0.573 | 0.487 | 0.922 |

#### Performance by difficulty

| Difficulty | n | Hit Rate | MRR | P@k | NDCG@k |
|------------|---|----------|-----|-----|--------|
| medium | 38 | 79% | 0.662 | 0.553 | 0.967 |
| easy | 9 | 67% | 0.556 | 0.511 | 0.758 |
| hard | 16 | 62% | 0.512 | 0.438 | 0.911 |

### Key Findings

**Strengths:**

1. **Semantic enrichment dramatically improves code retrieval.** HCPCS code lookup went from 14% to 57% hit rate. Three previously-failing HCPCS queries now succeed at rank 1 with perfect precision. The enrichment text provides category context that embeddings can leverage.

2. **Cross-source queries now achieve perfect MRR.** Queries spanning IOM policy and HCPCS codes (e.g., "Durable medical equipment coverage policy and HCPCS codes") now consistently rank relevant content at the top, up from MRR 0.675 to 1.000.

3. **Strong IOM and claims retrieval.** Claims/billing achieves 100% hit rate. IOM-sourced policy, payment, and compliance content retrieves reliably.

4. **Improved consistency.** Rephrased query pairs now retrieve more overlapping result sets (Jaccard 0.733 vs 0.483), particularly for cardiac rehabilitation topics.

5. **Fast retrieval.** Median latency of 6 ms per query with p95 at 8 ms, even on CPU.

**Weaknesses and areas for improvement:**

1. **LCD-specific queries remain weak (33% hit rate).** The main `lcd.csv` file with full LCD policy text exceeds Python's CSV field size limit and is not parsed. Only structural/relational MCD data is indexed.

2. **ICD-10-CM queries fail (no data).** Hypertension, chest pain, and diabetes foot ulcer ICD-10 queries cannot succeed without downloading ICD-10-CM data (requires `ICD10_CM_ZIP_URL`). The enrichment module is ready to tag these codes when data is available.

3. **TinyLlama answer quality is limited.** The 1.1B-parameter model produces verbose, repetitive answers. A larger model (7B+) would substantially improve answer quality.

### Recommendations

1. ~~**Improve code document embeddings.**~~ **Done.** Semantic enrichment now prepends category labels and related terms to HCPCS/ICD-10 documents. Code lookup hit rate improved from 14% to 57%.

2. **Parse full LCD text.** Increase Python's CSV field size limit to ingest the main `lcd.csv` file, which contains the full LCD policy text. This would dramatically improve LCD-specific retrieval.

3. **Add ICD-10-CM data.** Set `ICD10_CM_ZIP_URL` in `.env` to download and index ICD-10-CM codes. The enrichment module already supports ICD-10-CM chapter tagging.

4. **Upgrade the LLM.** Replace TinyLlama with a larger model (e.g., Mistral-7B, Llama-3-8B) for better answer synthesis, reduced repetition, and proper citation formatting.

5. **Improve cross-source retrieval.** Consider query expansion or hybrid search (keyword + semantic) to improve recall for queries that span IOM, MCD, and codes sources.

6. **Boost consistency.** For topics with fragmented content (like cardiac rehab), consider adding document-level summaries or topic clusters to improve retrieval stability across rephrasings.

## Configuration

Copy `.env.example` to `.env` and override as needed:

| Variable | Purpose |
|----------|----------|
| `DATA_DIR` | Root for `raw/`, `processed/`, `chroma/` (default: repo `data/`) |
| `EMBEDDING_MODEL` | sentence-transformers model (default: `all-MiniLM-L6-v2`). Changing it changes vector dimension; re-ingest or match the model used at index time. |
| `LOCAL_LLM_MODEL` | Hugging Face model (default: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`) |
| `LOCAL_LLM_DEVICE` | `auto`, `cpu`, or device map |
| `LOCAL_LLM_MAX_NEW_TOKENS` | Max tokens generated (default: 512). Invalid values fall back to default with a warning. |
| `LOCAL_LLM_REPETITION_PENALTY` | Repetition penalty (default: 1.05). Invalid values fall back to default with a warning. |
| `ICD10_CM_ZIP_URL` | Optional; for ICD-10-CM code download |
| `DOWNLOAD_TIMEOUT` | HTTP timeout in seconds for downloads (default: 60) |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | Text splitter defaults (1000 and 200). Optional tuning. |

## Testing

Install the dev optional dependency (includes pytest and ruff), then run:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

- **Config:** `tests/test_config.py` — safe env var parsing for numeric settings.
- **Download:** `tests/test_download.py` — mocked HTTP, idempotency, zip-slip and URL sanitization.
- **Ingest:** `tests/test_ingest.py` — extraction and chunking (including enrichment integration).
- **Enrichment:** `tests/test_enrich.py` — HCPCS/ICD-10-CM semantic enrichment (category labels, synonyms, edge cases).
- **Index:** `tests/test_index.py` — Chroma and embeddings (skipped when Chroma unavailable, e.g. some Python 3.14+ setups).
- **Query:** `tests/test_query.py` — retriever and RAG chain.
- **Validation/eval:** `tests/test_search_validation.py` — validation and eval question schema.
- **UI helpers:** `tests/test_app.py` — Streamlit app helpers (requires `.[ui]`).

No network or real downloads needed for the core suite; mocks are used for HTTP and external deps.

## Optional extras

- **`pip install -e ".[ui]"`** — Streamlit for the embedding search UI.
- **`pip install -e ".[dev]"`** — pytest (test suite) and ruff (linting/formatting). Required to run tests.
- **`pip install -e ".[unstructured]"`** — Fallback extractor for image-heavy PDFs when pdfplumber yields little text.

## Project layout

- **`src/medicare_rag/`** — Main package: `config`, `download/`, `ingest/` (including `enrich.py` for semantic enrichment), `index/`, `query/`.
- **`scripts/`** — CLI: `download_all.py`, `ingest_all.py`, `validate_and_eval.py`, `query.py`, `run_rag_eval.py`, `eval_questions.json`.
- **`tests/`** — Pytest suite.
- **`data/`** — Runtime data (gitignored): `raw/`, `processed/`, `chroma/`.

See **AGENTS.md** for detailed layout, conventions, and patterns.
