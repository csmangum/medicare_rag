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
- Output: `data/raw/<source>/` plus a `manifest.json` per source (URL, date, file list, optional SHA-256). Set `ICD10_CM_ZIP_URL` in `.env` if you want ICD-10-CM (see [CDC](https://www.cms.gov/nchs/icd/icd-10-cm.htm)).

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
