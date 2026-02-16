# medicare_rag

RAG POC for Medicare Revenue Cycle Management: ingest CMS manuals and coverage data, embed, and answer natural-language questions with cited sources.

## Phase 1: Data download

### Setup

1. **Create a virtual environment** (recommended for running and testing):

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. **Install the package** (editable, with dependencies):

   ```bash
   pip install -e .
   ```

3. **Environment**: Copy `.env.example` to `.env` and set any overrides (optional for Phase 1):

   ```bash
   cp .env.example .env
   ```

   For Phase 1 downloads you do not need API keys. Set `ICD10_CM_ZIP_URL` if you want to download ICD-10-CM code files (see [CDC ICD-10-CM](https://www.cdc.gov/nchs/icd/icd-10-cm.htm)).

### Download data

Run the download script from the repo root:

```bash
python scripts/download_all.py [--source iom|mcd|codes|all] [--force]
```

- `--source`: `iom` (IOM manuals 100-02, 100-03, 100-04), `mcd` (MCD bulk ZIP), `codes` (HCPCS + optional ICD-10-CM), or `all` (default).
- `--force`: Re-download and overwrite existing files; otherwise downloads are skipped when the file or manifest already exists.

Data is written under `data/raw/` (e.g. `data/raw/iom/`, `data/raw/mcd/`, `data/raw/codes/`). Each source directory includes a `manifest.json` with source URL, download date, and file list (with optional SHA-256 hashes). The codes manifest may include a `sources` list when both HCPCS and ICD-10-CM were downloaded.

### Tests

Run unit tests in the same venv:

```bash
pytest tests/ -v
```

Phase 1 tests live in `tests/test_download.py` (mocked HTTP, idempotency).

## Phase 3: Index (embed + vector store)

After extraction and chunking, run the full ingest to embed and store chunks:

```bash
python scripts/ingest_all.py [--source iom|mcd|codes|all] [--force]
```

This runs extract → chunk → embed → store. Use `--skip-index` to only extract and chunk (no embedding or vector store). The vector store is persisted at `data/chroma/` with collection name `medicare_rag`. Updates are incremental by content hash; only new or changed chunks are re-embedded and upserted. Hash lookup uses a full-colpus load into memory, so for very large corpora you may need a different strategy (e.g. batch get by chunk ids or a side index).

Chroma/embedding tests in `tests/test_index.py` are skipped when Chroma is unavailable (e.g. on Python 3.14+ with pydantic v1).

### Validate and evaluate index

After ingestion, validate the index and run retrieval evaluation:

```bash
python scripts/validate_and_eval.py              # validate + eval
python scripts/validate_and_eval.py --validate-only
python scripts/validate_and_eval.py --eval-only -k 10
python scripts/validate_and_eval.py --eval-only --json   # metrics as JSON
```

Validation checks that the Chroma collection exists, has documents, sample metadata (`doc_id`, `content_hash`), and that similarity search runs. Evaluation uses `scripts/eval_questions.json` (Medicare-focused queries with expected keywords/sources) and reports **hit rate** (fraction of queries with a relevant doc in top-k) and **MRR** (mean reciprocal rank). Add or edit entries in `eval_questions.json` to extend the eval set.

## Phase 4: Query (RAG with local LLM)

Run the interactive query REPL (after ingestion):

```bash
python scripts/query.py [--filter-source iom|mcd|codes] [--filter-manual 100-02] [--filter-jurisdiction JL] [-k 8]
```

Generation uses a local Hugging Face model (no API key). Configure via env (see `.env.example`):

- **`LOCAL_LLM_MODEL`** — Model id (default: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`).
- **`LOCAL_LLM_DEVICE`** — `auto` (default), `cpu`, or device map; use `cpu` on headless or when no GPU.
- **`CUDA_VISIBLE_DEVICES`** — Override GPU visibility (e.g. `CUDA_VISIBLE_DEVICES=""` for CPU-only).
- Optional: **`LOCAL_LLM_MAX_NEW_TOKENS`**, **`LOCAL_LLM_REPETITION_PENALTY`**.

## Phase 5: Testing and validation

### Unit tests

Run the full test suite (download, ingest, index, query) in the project venv:

```bash
pytest tests/ -v
```

Tests live in `tests/test_download.py`, `tests/test_ingest.py`, `tests/test_index.py`, and `tests/test_query.py`.

### Automated retrieval eval

Run retrieval evaluation (hit rate and MRR) using the same retriever as the RAG chain and the question set in `scripts/eval_questions.json`:

```bash
python scripts/validate_and_eval.py              # validate index + run eval
python scripts/validate_and_eval.py --eval-only -k 10
python scripts/validate_and_eval.py --eval-only --json   # metrics as JSON
```

Edit `scripts/eval_questions.json` to add or change questions (each entry: `id`, `query`, `expected_keywords`, `expected_sources`).

### Full-RAG eval (manual assessment)

To assess end-to-end answer quality and citation accuracy, run the full RAG chain (retriever + LLM) on the eval set and generate a report:

```bash
python scripts/run_rag_eval.py [--eval-file scripts/eval_questions.json] [--out data/rag_eval_report.md] [-k 8]
```

The script writes a markdown report (default: `data/rag_eval_report.md`) with each question, the generated answer, and cited source metadata. Open the report and manually assess whether answers are accurate and citations correct.
