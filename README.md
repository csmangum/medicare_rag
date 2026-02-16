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

Data is written under `data/raw/` (e.g. `data/raw/iom/`, `data/raw/mcd/`, `data/raw/codes/`). Each source directory includes a `manifest.json` with source URL, download date, and file list (with optional SHA-256 hashes).

### Tests

Run unit tests in the same venv:

```bash
pytest tests/ -v
```

Phase 1 tests live in `tests/test_download.py` (mocked HTTP, idempotency).
