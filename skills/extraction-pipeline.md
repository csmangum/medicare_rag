---
description: "Phase 2 extraction pipeline: converts raw PDFs, CSVs, and XML into plain text documents with metadata, handling diverse CMS data formats."
---

# Extraction Pipeline

The extraction pipeline (`src/medicare_rag/ingest/extract.py`) is Phase 2 of the [[rag-architecture]]. It transforms raw downloaded files into a uniform format: one `.txt` file containing the document's plain text and one `.meta.json` file with structured metadata.

## Extractors

- **IOM PDF extraction** — uses `pdfplumber` to extract text page by page; falls back to `unstructured` (if installed) for scanned/image PDFs that yield insufficient text (< 50 chars/page)
- **MCD CSV extraction** — reads CSV rows from [[mcd-bulk-data]], strips HTML using BeautifulSoup, and concatenates cell values into prose; each row becomes one document
- **HCPCS extraction** — parses the fixed-width [[hcpcs-level-ii]] text file, merging primary and continuation records, then applies [[semantic-enrichment-pipeline]] to prepend category context
- **ICD-10-CM extraction** — parses tabular XML from the [[icd-10-cm]] ZIP archive using `defusedxml` (when available) or standard `xml.etree`, then applies enrichment

## Metadata Schema

Every extracted document carries metadata:
- `source` — data origin (iom, mcd, codes)
- `manual` / `chapter` — for IOM documents
- `title` / `effective_date` / `jurisdiction` — for MCD documents
- `hcpcs_code` / `icd10_code` — for code documents
- `doc_id` — unique identifier used downstream

## Connections

The extraction pipeline consumes raw files from the [[download-pipeline]] and produces documents consumed by the [[chunking-strategy]]. Its output quality determines embedding quality in the [[vector-store]]. Enrichment ([[semantic-enrichment-pipeline]]) is applied during extraction to improve retrieval for code documents.
