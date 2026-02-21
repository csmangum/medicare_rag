---
description: "Embedding model: sentence-transformers/all-MiniLM-L6-v2 generates 384-dimensional vectors locally, with no API keys required."
---

# Embedding Model

The RAG system uses `sentence-transformers/all-MiniLM-L6-v2` to generate dense vector representations of document chunks and queries. This model runs locally, requires no API keys, and produces 384-dimensional embeddings.

## Model Characteristics

- **Architecture** — MiniLM (distilled BERT variant) fine-tuned on 1B+ sentence pairs
- **Dimensions** — 384 (compact, efficient for storage and similarity search)
- **Performance** — strong general-purpose semantic similarity; adequate for Medicare domain despite not being fine-tuned on medical text
- **Speed** — small enough to run on CPU; GPU accelerates batch embedding for large document sets
- **Configurable** — the model name is set via `EMBEDDING_MODEL` environment variable, allowing substitution with domain-specific medical embeddings if desired

## Why Local

Running embeddings locally means:
- No API costs or rate limits
- No data leaves the environment (important for [[hipaa-compliance]] if the system ever processes PHI)
- Reproducible results (same model version = same embeddings)
- Works offline after initial model download

## Connections

The embedding model is the bridge between the [[chunking-strategy]] (text in) and the [[vector-store]] (vectors out). Embedding quality determines [[retrieval-strategy]] effectiveness, which is measured by the [[eval-framework]]. The [[semantic-enrichment-pipeline]] improves embedding quality by adding domain vocabulary that the embedding model can leverage.
