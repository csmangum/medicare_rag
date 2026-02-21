# AGENTS.md

## Project Overview

Medicare RAG POC — a Retrieval-Augmented Generation system for Medicare Revenue Cycle Management. It ingests CMS manuals, coverage data, and coding files, embeds them into a vector store, and answers natural-language questions with cited sources.

**Language:** Python 3.11+
**Package manager:** pip / setuptools (see `pyproject.toml`)

## Repository Layout

```
src/medicare_rag/           # Main package (installed as editable via `pip install -e .`)
  __init__.py
  config.py                 # Paths, env config (DATA_DIR, models, batch sizes, chunking, hybrid/RRF tuning); safe int/float parsing; loads .env
  download/                 # Phase 1: download IOM manuals, MCD bulk data, HCPCS/ICD codes
    __init__.py              #   Re-exports download_iom, download_mcd, download_codes
    iom.py                   #   IOM chapter PDF scraper
    mcd.py                   #   MCD bulk ZIP downloader
    codes.py                 #   HCPCS + ICD-10-CM code file downloader
    _manifest.py             #   Manifest writing and SHA-256 hashing
    _utils.py                #   URL sanitization, stream_download helper, DOWNLOAD_TIMEOUT (from config)
  ingest/                   # Phase 2: text extraction, enrichment, chunking, clustering, and summarization
    __init__.py              #   SourceKind type (imported by extract, chunk)
    extract.py               #   PDF/text extraction (pdfplumber, optional unstructured fallback); defusedxml for XML when available
    enrich.py                #   HCPCS/ICD-10 semantic enrichment (category labels, synonyms, related terms)
    chunk.py                 #   LangChain text splitters (uses CHUNK_SIZE, CHUNK_OVERLAP, LCD_CHUNK_SIZE, LCD_CHUNK_OVERLAP from config); optional summary generation
    cluster.py               #   Topic clustering: keyword-pattern-based assignment of chunks to clinical/policy topics; loads topic_definitions.json
    summarize.py             #   Extractive summarization: TF-IDF sentence scoring for document-level and topic-cluster summary generation
  index/                    # Phase 3: embedding and vector store
    __init__.py              #   Re-exports get_embeddings, get_or_create_chroma, upsert_documents
    embed.py                 #   sentence-transformers embeddings
    store.py                 #   ChromaDB upsert, incremental by content hash; get_raw_collection helper
  query/                    # Phase 4: retrieval and RAG chain
    __init__.py              #   Imports and exposes expand, hybrid, retriever, and chain submodules
    retriever.py             #   LCDAwareRetriever with LCD query expansion, topic summary boosting/injection, and get_retriever factory
    expand.py                #   Cross-source query expansion: detects source relevance (IOM/MCD/codes), generates source-targeted variants with synonym expansion
    hybrid.py                #   HybridRetriever: fuses semantic + BM25 keyword search via Reciprocal Rank Fusion (RRF) with cross-source diversification
    chain.py                 #   Local LLM (HuggingFace) RAG chain
app.py                      # Streamlit UI for embedding search (launch: `streamlit run app.py`; requires .[ui])
scripts/                    # CLI entry points
  download_all.py            #   Bulk download (--source iom|mcd|codes|all, --force)
  ingest_all.py              #   Extract, chunk, embed, store (--source, --force, --skip-extract, --skip-index, --no-summaries)
  validate_and_eval.py       #   Index validation + retrieval eval (hit rate, MRR)
  query.py                   #   Interactive RAG REPL
  run_rag_eval.py            #   Full-RAG eval report generation
  eval_questions.json        #   Eval question set (expected keywords/sources)
tests/                      # Unit tests (pytest; install with pip install -e ".[dev]")
  conftest.py                #   Shared fixtures (autouse: reset BM25 index after each test)
  test_config.py             #   Safe env int/float parsing
  test_download.py           #   Mocked HTTP, idempotency, zip-slip and URL sanitization
  test_ingest.py             #   Extraction and chunking tests (including enrichment integration)
  test_enrich.py             #   HCPCS/ICD-10-CM semantic enrichment tests
  test_cluster.py            #   Topic clustering: assign_topics, cluster_documents, tag_documents_with_topics, topic definition validation
  test_summarize.py          #   Extractive summarization: sentence splitting, scoring, document/topic summary generation, chunk integration
  test_index.py              #   Chroma/embedding and get_raw_collection tests (skipped when Chroma unavailable)
  test_query.py              #   Retriever and chain tests
  test_retriever_boost.py    #   Summary document boosting, topic injection, and LCDAwareRetriever summary integration
  test_hybrid.py             #   Hybrid retriever, cross-source query expansion, BM25 index, RRF, source diversity
  test_search_validation.py  #   Search/validation tests
  test_app.py                #   Streamlit app helpers (escape, filters; requires .[ui])
data/                       # Runtime data directory (gitignored)
  raw/                       #   Downloaded source files
  processed/                 #   Extracted/chunked text
  chroma/                    #   ChromaDB vector store
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

Always use a virtual environment. Install the dev optional dependency (includes pytest and rank-bm25), then run:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Tests use `unittest.mock` to mock HTTP calls and external dependencies. No network access or real data downloads are needed. Some index tests are skipped automatically when ChromaDB is unavailable (e.g., on newer Python versions with pydantic v1 incompatibility). A shared `conftest.py` fixture resets the BM25 singleton index after each test for isolation.

## Code Style and Quality

- Formatter/linter: **ruff** (install via `pip install -e ".[dev]"`)
- Ruff config: `target-version = "py311"`, `line-length = 100`, rules `E, F, W, I, B, UP`
- No backwards compatibility constraints — refactor freely as needed
- Type hints are used throughout; follow existing patterns
- All source code lives under `src/medicare_rag/` with the `pythonpath` set in `pyproject.toml`

## Key Conventions

- **Configuration** is centralized in `src/medicare_rag/config.py`. It reads from environment variables (via `python-dotenv`) with sensible defaults. Numeric settings use safe parsing (`_safe_int`, `_safe_float`, `_safe_positive_int`, `_safe_float_positive`): invalid values log a warning and fall back to the default. Key settings:
  - Paths: `DATA_DIR`, `RAW_DIR`, `PROCESSED_DIR`, `CHROMA_DIR`
  - Models: `EMBEDDING_MODEL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_DEVICE`, `LOCAL_LLM_MAX_NEW_TOKENS`, `LOCAL_LLM_REPETITION_PENALTY`
  - Chunking: `CHUNK_SIZE`, `CHUNK_OVERLAP`, `LCD_CHUNK_SIZE`, `LCD_CHUNK_OVERLAP`
  - Retrieval: `LCD_RETRIEVAL_K`, `HYBRID_SEMANTIC_WEIGHT`, `HYBRID_KEYWORD_WEIGHT`, `RRF_K`, `CROSS_SOURCE_MIN_PER_SOURCE`, `MAX_QUERY_VARIANTS`
  - Summarization: `ENABLE_TOPIC_SUMMARIES`, `MAX_DOC_SUMMARY_SENTENCES`, `MAX_TOPIC_SUMMARY_SENTENCES`, `MIN_TOPIC_CLUSTER_CHUNKS`, `MIN_DOC_TEXT_LENGTH_FOR_SUMMARY`
  - Batching: `DOWNLOAD_TIMEOUT`, `CHROMA_UPSERT_BATCH_SIZE`, `GET_META_BATCH_SIZE`, `CSV_FIELD_SIZE_LIMIT`
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
- The Streamlit app and index store use `get_raw_collection(store)` from `index.store` to access the Chroma wrapper's underlying collection for batched metadata and dimension checks; this wraps the private `_collection` API and may need updating if langchain-chroma changes.
- The hybrid retriever (`query/hybrid.py`) maintains a module-level singleton `BM25Index` that is lazily built from the Chroma collection and checked for staleness by document count. Use `reset_bm25_index()` in tests to avoid state leaking between test cases.
- Topic definitions for clustering are loaded from `DATA_DIR/topic_definitions.json` if present, otherwise from the package default at `src/medicare_rag/data/topic_definitions.json`. Add new topics by extending the JSON file.

## Retrieval Architecture

The retrieval pipeline has two retriever implementations selected by `get_retriever()`:

1. **`HybridRetriever`** (default when `rank-bm25` is installed via `.[dev]` or `.[hybrid]`):
   - Expands queries into source-targeted variants via `query.expand` (IOM/MCD/codes vocabulary)
   - Runs semantic search (Chroma) and BM25 keyword search for each variant
   - Merges results via **Reciprocal Rank Fusion** (RRF) with configurable weights (`HYBRID_SEMANTIC_WEIGHT`, `HYBRID_KEYWORD_WEIGHT`)
   - Applies **cross-source diversification** (`ensure_source_diversity`) to guarantee minimum representation from each relevant source type
   - LCD-specific queries trigger additional MCD-focused searches
   - The BM25 index is a thread-safe singleton (`BM25Index`) that lazily builds from Chroma and detects staleness by document count

2. **`LCDAwareRetriever`** (fallback when `rank-bm25` is unavailable):
   - For LCD queries: runs multi-variant MCD-filtered searches + base search, deduplicates via round-robin interleaving
   - For non-LCD queries: standard similarity search

Both retrievers apply **topic summary boosting**: `detect_query_topics` identifies relevant clinical topics, `inject_topic_summaries` fetches anchor docs from the store, and `boost_summaries` promotes them to the top of results.

## Topic Clustering and Summarization

The ingest pipeline optionally generates summary documents (controlled by `ENABLE_TOPIC_SUMMARIES` / `--no-summaries`):

1. **Topic clustering** (`ingest/cluster.py`): keyword-pattern-based assignment of chunks to clinical topics (cardiac rehab, wound care, imaging, DME, etc.). Topic definitions are loaded from `data/topic_definitions.json` (or the package default). A chunk may belong to multiple topics.

2. **Extractive summarization** (`ingest/summarize.py`): generates two types of summary `Document` objects:
   - **Document-level summaries** (`doc_type=document_summary`): TF-IDF sentence scoring over full extracted text
   - **Topic-cluster summaries** (`doc_type=topic_summary`): consolidates top sentences across all chunks in a topic cluster

Summary documents are indexed alongside regular chunks and act as stable "anchor" chunks that improve retrieval consistency across query rephrasings.

## Optional Dependencies

Defined in `pyproject.toml` under `[project.optional-dependencies]`:

- **`dev`**: `ruff`, `pytest`, `rank-bm25` — for linting, testing, and hybrid retrieval
- **`ui`**: `streamlit` — for the embedding search UI (`app.py`)
- **`hybrid`**: `rank-bm25` — for hybrid (semantic + keyword) retrieval only
- **`unstructured`**: `unstructured` — PDF fallback for scanned/image PDFs
