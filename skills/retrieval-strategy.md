---
description: "Retrieval strategy: Chroma-backed similarity search with metadata filters that narrows results by source type, jurisdiction, or code system."
---

# Retrieval Strategy

The retrieval module (`src/medicare_rag/query/retriever.py`) is the query-time component that finds the most relevant document chunks for a user's question. It performs similarity search over the [[vector-store]] and returns the top-k results as context for the [[generation-chain]].

## How It Works

1. The user's natural-language question is embedded using the same [[embedding-model]] used to index documents
2. ChromaDB performs approximate nearest-neighbor search to find the most similar document chunk vectors
3. Optional metadata filters narrow results (e.g., only LCD documents, only a specific MAC jurisdiction)
4. The top-k results (with their text and metadata) are returned as retrieval context

## Retrieval Quality

Retrieval quality is the primary bottleneck in RAG systems — if the right documents aren't retrieved, the LLM can't generate a correct answer. Quality depends on:
- [[Embedding-model]] choice and the semantic alignment between queries and documents
- [[Semantic-enrichment-pipeline]] bridging vocabulary gaps between user language and code descriptions
- [[Chunking-strategy]] ensuring that relevant information isn't split across chunk boundaries
- The diversity and coverage of indexed documents from [[iom-manuals]], [[mcd-bulk-data]], and code files

## Connections

Retrieval connects the [[vector-store]] to the [[generation-chain]]. Its quality is measured by the [[eval-framework]] using hit rate and MRR metrics. Retrieval failures for specific query types can guide improvements to the [[semantic-enrichment-pipeline]] or [[chunking-strategy]].
