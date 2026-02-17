# Medicare RAG

A **Retrieval-Augmented Generation (RAG)** proof-of-concept for Medicare Revenue Cycle Management. It ingests CMS manuals, coverage determinations, and coding files; embeds them in a vector store; and answers natural-language questions with cited sources. Everything runs locally—no API keys required.

## What it does

- **Download** — IOM manuals (100-02, 100-03, 100-04), MCD bulk data, HCPCS and optional ICD-10-CM code files into `data/raw/`.
- **Ingest** — Extract text (PDF and structured sources), chunk with LangChain splitters, embed with sentence-transformers, and upsert into ChromaDB with incremental updates by content hash.
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

- **Extract:** PDFs (pdfplumber; optional `unstructured` for image-heavy PDFs), MCD/codes from structured files.
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
- **Evaluation:** Uses `scripts/eval_questions.json` (Medicare queries with expected keywords/sources). Reports **hit rate** (relevant doc in top-k) and **MRR** (mean reciprocal rank). Edit `eval_questions.json` to extend the set.

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

Full pipeline evaluation run on 2026-02-17 using default settings (embedding model: `all-MiniLM-L6-v2`, LLM: `TinyLlama-1.1B-Chat-v1.0`, chunk size: 1000, overlap: 200, k=5). Data sources: IOM manuals 100-02/03/04, MCD bulk data, and HCPCS codes (ICD-10-CM not included in this run).

### Index Summary

| Metric | Value |
|--------|-------|
| Total documents (chunks) | 41,802 |
| IOM chunks | 16,916 (40.5%) |
| MCD chunks | 15,881 (38.0%) |
| Codes chunks | 9,005 (21.5%) |
| Embedding dimension | 384 |
| Content length (median) | 488 chars |
| Content length (p5–p95) | 82–989 chars |
| Validation checks | 23/23 passed |
| Duplicate IDs | 0 |
| Empty documents | 0 |

### Retrieval Evaluation (63 questions, k=5)

| Metric | Value |
|--------|-------|
| **Hit Rate** | **87.3%** (55/63) |
| **MRR** | **0.8325** |
| **Avg Precision@5** | **0.7619** |
| **Avg NDCG@5** | **0.9516** |
| Median latency | 6 ms |
| p95 latency | 7 ms |

#### Multi-k sweep

| k | Hit Rate | MRR | P@k | NDCG@k |
|---|----------|-----|-----|--------|
| 1 | 81.0% | 0.810 | 0.810 | 0.968 |
| 3 | 84.1% | 0.825 | 0.762 | 0.962 |
| 5 | 87.3% | 0.833 | 0.762 | 0.952 |
| 10 | 92.1% | 0.839 | 0.724 | 0.943 |

#### Performance by category

| Category | n | Hit Rate | MRR | P@k | NDCG@k |
|----------|---|----------|-----|-----|--------|
| claims_billing | 6 | 100% | 1.000 | 1.000 | 1.000 |
| coding_modifiers | 5 | 100% | 1.000 | 0.960 | 1.000 |
| policy_coverage | 6 | 100% | 1.000 | 0.933 | 0.992 |
| appeals_denials | 5 | 100% | 1.000 | 0.920 | 0.992 |
| payment | 3 | 100% | 1.000 | 0.933 | 0.993 |
| consistency | 4 | 100% | 1.000 | 0.950 | 0.989 |
| edge_case | 4 | 100% | 1.000 | 0.900 | 0.984 |
| compliance | 3 | 100% | 1.000 | 0.800 | 0.983 |
| abbreviation | 5 | 100% | 0.900 | 0.960 | 0.978 |
| semantic_retrieval | 5 | 100% | 0.850 | 0.720 | 0.958 |
| cross_source | 4 | 100% | 0.675 | 0.700 | 0.908 |
| lcd_policy | 6 | 67% | 0.667 | 0.433 | 0.986 |
| **code_lookup** | **7** | **14%** | **0.143** | **0.086** | **0.714** |

#### Performance by expected source

| Source | n | Hit Rate | MRR | P@k | NDCG@k |
|--------|---|----------|-----|-----|--------|
| iom | 52 | 100% | 0.951 | 0.892 | 0.982 |
| mcd | 16 | 88% | 0.828 | 0.738 | 0.981 |
| codes | 18 | 67% | 0.567 | 0.556 | 0.862 |

#### Performance by difficulty

| Difficulty | n | Hit Rate | MRR | P@k | NDCG@k |
|------------|---|----------|-----|-----|--------|
| medium | 38 | 92% | 0.888 | 0.837 | 0.988 |
| hard | 16 | 88% | 0.794 | 0.662 | 0.965 |
| easy | 9 | 67% | 0.667 | 0.622 | 0.772 |

#### Consistency (rephrased query overlap)

| Group | Jaccard Score |
|-------|---------------|
| wheelchair | 0.800 |
| cardiac_rehab | 0.167 |
| **Average** | **0.483** |

### Key Findings

**Strengths:**

1. **Excellent IOM retrieval.** All 52 questions expecting IOM content achieved 100% hit rate with MRR 0.951. The system reliably retrieves policy coverage, claims billing, appeals, payment, and compliance content from CMS manuals.

2. **Strong performance across most categories.** Claims/billing, coding modifiers, policy coverage, appeals, payment, compliance, edge cases, consistency, and abbreviation categories all achieved 100% hit rate.

3. **Good semantic understanding.** Natural-language and conversational queries (e.g., "Will Medicare pay for an ambulance ride?", "Is my surgery going to be covered?") achieve 100% hit rate, demonstrating that the embedding model handles paraphrasing well.

4. **Abbreviation resolution works.** SNF, DME, ASC, MAC, and OPPS abbreviations all resolve correctly to the relevant content with 100% hit rate.

5. **Fast retrieval.** Median latency of 6 ms per query with p95 at 7 ms, even on CPU.

6. **Robust edge-case handling.** Single-word queries ("Medicare"), specific manual references ("IOM 100-04 Chapter 1"), multi-concept queries, and negation queries all pass.

**Weaknesses and areas for improvement:**

1. **Code lookup is the weakest category (14% hit rate).** Most HCPCS code-specific queries fail to retrieve documents from the `codes` source. The code documents are very short (one per HCPCS/ICD code when both sources are enabled), and their content (`Code: X1234\n\nLong description: ...`) doesn't embed well against natural-language queries like "What HCPCS codes are used for durable medical equipment?" The retriever tends to return IOM policy chunks that mention these topics instead of the actual code records. Only the COPD query succeeded because "obstructive pulmonary" matched code descriptions directly. In this run, ICD-10-CM data was not included (no `ICD10_CM_ZIP_URL` provided), so hypertension and chest pain ICD-10 queries could not retrieve any ICD-10-CM code records at all (NDCG=0).

2. **LCD-specific queries underperform (67% hit rate).** Questions targeting specific LCD policies (e.g., "Does Novitas (JL) have an LCD for cardiac rehab?", "What LCDs apply to outpatient physical therapy?") fail because the MCD data is largely relational CSV metadata (contractor IDs, revision histories, code cross-references) rather than rich policy text. The main `lcd.csv` file with full LCD text exceeds Python's CSV field size limit and is not parsed, leaving only structural/relational data in the index.

3. **Consistency is mixed (avg Jaccard 0.483).** Wheelchair queries show good consistency (0.800 overlap), but cardiac rehab queries retrieve substantially different document sets when rephrased (0.167). This suggests retrieval stability varies by topic — the cardiac rehab corpus spans many heterogeneous chunks.

4. **"Easy" difficulty questions score lower than "medium" or "hard" (67% vs 92%/88%).** This is driven by code_lookup "easy" questions (HCPCS general, ICD-10 hypertension, chest pain) all failing. The difficulty labels reflect domain complexity, not retrieval difficulty — simple code lookups are actually harder for a semantic retrieval system.

5. **Cross-source retrieval is adequate but imperfect (MRR 0.675).** Questions spanning multiple sources (IOM + codes, IOM + MCD) find relevant content but sometimes rank it lower. DME coverage + codes had the relevant document at rank 5.

6. **TinyLlama answer quality is limited.** The 1.1B-parameter model produces verbose, repetitive answers that often re-state context rather than synthesizing it. It echoes the system prompt in outputs and truncates mid-sentence at the 512-token limit. A larger model (7B+) or an API-based LLM would substantially improve answer quality.

### Recommendations

1. **Improve code document embeddings.** Enrich HCPCS/ICD-10 document text with category labels, synonyms, and related terms (e.g., "HCPCS E-codes: durable medical equipment, wheelchair, hospital bed") to improve semantic match with natural-language queries.

2. **Parse full LCD text.** Increase Python's CSV field size limit to ingest the main `lcd.csv` file, which contains the full LCD policy text. This would dramatically improve LCD-specific retrieval.

3. **Add ICD-10-CM data.** Set `ICD10_CM_ZIP_URL` in `.env` to download and index ICD-10-CM codes for diagnosis code lookup queries.

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
- **Ingest:** `tests/test_ingest.py` — extraction and chunking.
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

- **`src/medicare_rag/`** — Main package: `config`, `download/`, `ingest/`, `index/`, `query/`.
- **`scripts/`** — CLI: `download_all.py`, `ingest_all.py`, `validate_and_eval.py`, `query.py`, `run_rag_eval.py`, `eval_questions.json`.
- **`tests/`** — Pytest suite.
- **`data/`** — Runtime data (gitignored): `raw/`, `processed/`, `chroma/`.

See **AGENTS.md** for detailed layout, conventions, and patterns.
