---
description: "ChromaDB vector store: persists embeddings at data/chroma/ with incremental upsert by content hash, supporting similarity search with metadata filtering."
---

# Vector Store

The vector store (`src/medicare_rag/index/store.py`) is the persistence and retrieval layer of the [[rag-architecture]]. It uses ChromaDB to store document embeddings with metadata, enabling similarity search over the entire Medicare knowledge corpus.

## Implementation

- **Database** — ChromaDB (local, persistent at `data/chroma/`)
- **Collection** — single collection named `medicare_rag`
- **Incremental upsert** — documents are identified by content hash; re-indexing only adds/updates changed documents, making the process efficient for incremental updates
- **Batch size** — configurable via `CHROMA_UPSERT_BATCH_SIZE` (default 5000) and `GET_META_BATCH_SIZE` (default 500)

## Metadata

Each embedded chunk carries metadata from the [[extraction-pipeline]]:
- `source` — data origin (iom, mcd, codes)
- `doc_id` — unique document identifier
- `title`, `jurisdiction`, `effective_date` — for filtered retrieval
- `hcpcs_code`, `icd10_code` — for code-specific queries

This metadata enables the [[retrieval-strategy]] to filter results by source type, jurisdiction, or code system.

## Access Pattern

The `get_raw_collection(store)` utility provides access to ChromaDB's underlying collection for batched metadata queries and dimension checks. This wraps the private `_collection` API and may need updating if the langchain-chroma integration changes.

## Connections

The vector store sits between the [[embedding-model]] (which produces vectors) and the [[retrieval-strategy]] (which queries them). It persists the indexed knowledge that the [[generation-chain]] uses to produce answers. The [[eval-framework]] validates retrieval quality against this store.
