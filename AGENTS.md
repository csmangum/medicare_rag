# AGENTS.md

## Project Overview

Medicare RAG POC — a Retrieval-Augmented Generation system for Medicare Revenue Cycle Management. It ingests CMS manuals, coverage data, and coding files, embeds them into a vector store, and answers natural-language questions with cited sources.

**Language:** Python 3.11+
**Package manager:** pip / setuptools (see `pyproject.toml`)

## Repository Layout

```
src/medicare_rag/           # Main package (installed as editable via `pip install -e .`)
  config.py                 # Paths, env config (DATA_DIR, model settings); loads .env
  download/                 # Phase 1: download IOM manuals, MCD bulk data, HCPCS/ICD codes
    iom.py                  #   IOM chapter PDF scraper
    mcd.py                  #   MCD bulk ZIP downloader
    codes.py                #   HCPCS + ICD-10-CM code file downloader
    _manifest.py            #   Manifest writing and SHA-256 hashing
    _utils.py               #   URL sanitization helpers
  ingest/                   # Phase 2: text extraction and chunking
    extract.py              #   PDF/text extraction (pdfplumber, optional unstructured fallback)
    chunk.py                #   LangChain text splitters
  index/                    # Phase 3: embedding and vector store
    embed.py                #   sentence-transformers embeddings
    store.py                #   ChromaDB upsert, incremental by content hash
  query/                    # Phase 4: retrieval and RAG chain
    retriever.py            #   Chroma-backed retriever
    chain.py                #   Local LLM (HuggingFace) RAG chain
scripts/                    # CLI entry points
  download_all.py           #   Bulk download (--source iom|mcd|codes|all, --force)
  ingest_all.py             #   Extract, chunk, embed, store (--source, --force, --skip-index)
  validate_and_eval.py      #   Index validation + retrieval eval (hit rate, MRR)
  query.py                  #   Interactive RAG REPL
  run_rag_eval.py           #   Full-RAG eval report generation
  eval_questions.json       #   Eval question set (expected keywords/sources)
tests/                      # Unit tests (pytest)
  test_download.py          #   Mocked HTTP, idempotency, zip-slip protection
  test_ingest.py            #   Extraction and chunking tests
  test_index.py             #   Chroma/embedding tests (skipped when Chroma unavailable)
  test_query.py             #   Retriever and chain tests
  test_search_validation.py #   Search/validation tests
data/                       # Runtime data directory (gitignored)
  raw/                      #   Downloaded source files
  processed/                #   Extracted/chunked text
  chroma/                   #   ChromaDB vector store
```

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install the package in editable mode:
   ```bash
   pip install -e .
   ```
3. Copy `.env.example` to `.env` for optional configuration overrides. No API keys are required — embeddings and LLM inference run locally via sentence-transformers and HuggingFace.

## Running Tests

Always use a virtual environment. Run the full test suite with:

```bash
pytest tests/ -v
```

Tests use `unittest.mock` to mock HTTP calls and external dependencies. No network access or real data downloads are needed. Some index tests are skipped automatically when ChromaDB is unavailable (e.g., on newer Python versions with pydantic v1 incompatibility).

## Code Style and Quality

- Formatter/linter: **ruff** (install via `pip install -e ".[dev]"`)
- No backwards compatibility constraints — refactor freely as needed
- Type hints are used throughout; follow existing patterns
- All source code lives under `src/medicare_rag/` with the `pythonpath` set in `pyproject.toml`

## Key Conventions

- **Configuration** is centralized in `src/medicare_rag/config.py`. It reads from environment variables (via `python-dotenv`) with sensible defaults. Override paths with `DATA_DIR`, model settings with `EMBEDDING_MODEL`, `LOCAL_LLM_MODEL`, etc.
- **Idempotent operations**: downloads check for existing manifests/files before re-downloading. Index upserts are incremental by content hash. Use `--force` to override.
- **Manifests**: each download source writes a `manifest.json` with source URL, download date, and file list (with optional SHA-256 hashes).
- **No API keys**: the system uses local sentence-transformers for embeddings and a local HuggingFace model (default: TinyLlama) for generation. No external API calls for inference.

## Important Patterns

- HTTP clients use `httpx` with context managers and streaming for large downloads
- ZIP extraction uses a safe extractor (`_safe_extract_zip`) that guards against zip-slip path traversal
- The vector store (ChromaDB) persists at `data/chroma/` with collection name `medicare_rag`
- Embedding model default: `sentence-transformers/all-MiniLM-L6-v2`
- LLM default: `TinyLlama/TinyLlama-1.1B-Chat-v1.0` (configurable via env)
- Tests follow the pattern: fixture creates `tmp_path`, mocks are applied via `unittest.mock.patch`, assertions verify file creation and manifest contents
