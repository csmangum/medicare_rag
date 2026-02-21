---
description: "Chunking strategy: LangChain text splitters break extracted documents into overlapping chunks optimized for embedding and retrieval."
---

# Chunking Strategy

Chunking (`src/medicare_rag/ingest/chunk.py`) is the process of splitting extracted documents into smaller pieces suitable for embedding. The chunk size must balance context completeness (larger chunks retain more meaning) against retrieval precision (smaller chunks match more specific queries).

## Configuration

- **CHUNK_SIZE** — default 1000 characters; configurable via environment variable
- **CHUNK_OVERLAP** — default 200 characters; ensures that information spanning a chunk boundary is captured in at least one chunk
- Both values are validated at startup in `config.py` (size >= 1, 0 <= overlap < size)

## Splitter

The pipeline uses LangChain's `RecursiveCharacterTextSplitter`, which splits on a hierarchy of separators (paragraph breaks > line breaks > sentence boundaries > word boundaries) to keep semantically coherent units together.

## Document-Type Considerations

- **IOM chapters** — long regulatory text; 1000-char chunks provide enough context for policy questions while keeping retrieval focused
- **LCD/NCD documents** — structured policy documents; chunks may split across sections (coverage criteria vs. billing guidance), which overlap mitigates
- **HCPCS/ICD-10 documents** — short code descriptions (often < 1000 chars after enrichment); many code documents fit in a single chunk, preserving the enrichment preamble and code description together

## Connections

Chunking follows the [[extraction-pipeline]] and precedes embedding in the [[vector-store]]. Chunk quality directly affects retrieval relevance in the [[retrieval-strategy]]. Chunk size is an open tuning parameter noted in the [[index]] explorations — optimal size may differ for dense regulatory text vs. sparse code descriptions.
