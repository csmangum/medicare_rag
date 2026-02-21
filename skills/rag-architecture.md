---
description: "Map of Content for the Medicare RAG system architecture: the four-phase pipeline (download, ingest, index, query) and how each phase transforms CMS data into retrievable, citable answers."
---

# RAG Architecture

This project implements a Retrieval-Augmented Generation pipeline purpose-built for Medicare domain knowledge. The architecture follows four phases, each mapping to a package under `src/medicare_rag/`. The system exists because [[rag-bridges-the-knowledge-gap]] — no human can hold the full corpus of CMS manuals, coverage determinations, and code definitions in working memory.

## Phase 1: Download

- [[download-pipeline]] — orchestrates retrieval of three source types: IOM chapter PDFs, MCD bulk data ZIPs, and HCPCS/ICD-10 code files; each source writes a manifest with SHA-256 hashes for idempotent re-runs
- [[iom-manuals]] — the Internet-Only Manuals (100-02 Benefits Policy, 100-03 NCD, 100-04 Claims Processing) scraped as chapter PDFs from the CMS website
- [[mcd-bulk-data]] — the Medicare Coverage Database bulk export containing LCDs, NCDs, and Articles as CSV-in-ZIP archives

## Phase 2: Ingest

- [[extraction-pipeline]] — PDF text extraction (pdfplumber with unstructured fallback), CSV parsing with HTML stripping, and XML parsing for ICD-10-CM; produces one `.txt` + `.meta.json` per logical document
- [[semantic-enrichment-pipeline]] — prepends category labels and related terms to HCPCS and ICD-10 documents so embedding vectors align with natural-language queries (e.g., "wheelchair" → E-codes)
- [[chunking-strategy]] — LangChain text splitters break documents into overlapping chunks (default 1000 chars, 200 overlap); chunk size is configurable because optimal size differs between dense regulatory text and sparse code descriptions

## Phase 3: Index

- [[embedding-model]] — sentence-transformers/all-MiniLM-L6-v2 generates 384-dimensional vectors; runs locally with no API keys required
- [[vector-store]] — ChromaDB persists embeddings at `data/chroma/` with incremental upsert by content hash; the collection `medicare_rag` holds all document types with metadata for filtered retrieval

## Phase 4: Query

- [[retrieval-strategy]] — Chroma-backed retriever performs similarity search over the vector store; metadata filters can narrow results by source type, jurisdiction, or code system
- [[generation-chain]] — a local HuggingFace LLM (default TinyLlama) receives retrieved chunks as context and generates answers with source citations; no external API calls

## Evaluation

- [[eval-framework]] — hit-rate and MRR metrics over a curated question set; validates that retrieval surfaces the right documents for known Medicare questions

## Connections

The RAG pipeline is the technical implementation serving [[revenue-cycle-management]] teams. It ingests the data described in [[medicare-fundamentals]], indexes the codes from [[billing-and-coding]], retrieves the policies from [[coverage-determination]], and helps navigate the [[claims-lifecycle]]. Its answers must be accurate enough to support [[compliance-and-regulations]] decisions.
