---
description: "Phase 1 download pipeline: orchestrates retrieval of IOM PDFs, MCD bulk data, and HCPCS/ICD-10 code files with idempotent manifests and SHA-256 hashing."
---

# Download Pipeline

The download pipeline (`src/medicare_rag/download/`) is Phase 1 of the [[rag-architecture]]. It retrieves raw Medicare data from CMS websites and stores it locally with manifests for idempotent re-runs. The pipeline is invoked via `scripts/download_all.py` with `--source iom|mcd|codes|all`.

## Data Sources

- [[iom-manuals]] — IOM chapter PDFs scraped from CMS; organized by manual ID (100-02, 100-03, 100-04)
- [[mcd-bulk-data]] — Medicare Coverage Database bulk export (LCDs, NCDs, Articles) as ZIP archives
- HCPCS code file — fixed-width text file of all [[hcpcs-level-ii]] codes
- ICD-10-CM code file — ZIP containing tabular XML of [[icd-10-cm]] codes

## Idempotency

Each download writes a `manifest.json` containing the source URL, download date, and a list of files with optional SHA-256 hashes. On subsequent runs, the pipeline checks for existing manifests and skips already-downloaded files unless `--force` is specified. This ensures bandwidth-efficient re-runs and reproducible data states.

## Implementation Details

- HTTP client: `httpx` with context managers and streaming for large files
- ZIP safety: `_safe_extract_zip` guards against zip-slip path traversal attacks
- URL sanitization: input URLs are validated before download
- Timeout: configurable via `DOWNLOAD_TIMEOUT` in config (default 60s)

## Connections

The download pipeline produces raw files consumed by the [[extraction-pipeline]] in Phase 2. Its manifest system supports incremental processing across the full pipeline. Configuration is centralized in `src/medicare_rag/config.py`.
