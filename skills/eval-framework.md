---
description: "Evaluation framework: hit-rate and MRR metrics over a curated question set that validates retrieval quality against known Medicare questions."
---

# Evaluation Framework

The evaluation framework (`scripts/validate_and_eval.py` and `scripts/run_rag_eval.py`) measures the RAG system's ability to retrieve relevant documents for known Medicare questions. It is the feedback loop that validates changes to the [[embedding-model]], [[semantic-enrichment-pipeline]], [[chunking-strategy]], and [[retrieval-strategy]].

## Metrics

- **Hit rate** — the percentage of evaluation questions where at least one relevant document appears in the top-k retrieved results; measures recall
- **Mean Reciprocal Rank (MRR)** — the average of the reciprocal of the rank of the first relevant document; rewards retrieval systems that put the best result first

## Evaluation Set

The curated question set (`scripts/eval_questions.json`) contains:
- Natural-language questions about Medicare topics
- Expected keywords that should appear in retrieved documents
- Expected source types (iom, mcd, codes) that should be represented in results

## Usage

- **Index validation** — verifies that the [[vector-store]] is populated with expected document types and embedding dimensions match the [[embedding-model]]
- **Retrieval evaluation** — runs the evaluation question set against the retriever and computes hit rate and MRR
- **RAG evaluation** — tests end-to-end through the [[generation-chain]] and evaluates answer quality

## Connections

The evaluation framework is the quality gate for the entire [[rag-architecture]]. It was used to validate the [[semantic-enrichment-pipeline]] improvement (showing gains in hit rate for code-related queries). It connects to every upstream pipeline component because changes to [[download-pipeline]], [[extraction-pipeline]], [[chunking-strategy]], [[embedding-model]], or [[vector-store]] configuration can affect retrieval quality.
