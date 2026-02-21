---
description: "Generation chain: a local HuggingFace LLM (default TinyLlama) receives retrieved chunks and generates answers with source citations."
---

# Generation Chain

The generation chain (`src/medicare_rag/query/chain.py`) is the final component of the [[rag-architecture]]. It takes the user's question and retrieved document chunks from the [[retrieval-strategy]], formats them into a prompt, and generates a natural-language answer with source citations.

## Implementation

- **LLM** — HuggingFace pipeline using a local model (default: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`)
- **Device** — configurable via `LOCAL_LLM_DEVICE` (default: auto); supports CPU and GPU
- **Parameters** — `max_new_tokens` (default 512) and `repetition_penalty` (default 1.05) are configurable via environment variables
- **No API keys** — the entire inference stack runs locally

## Prompt Design

The chain formats a prompt that:
1. Provides system instructions for answering Medicare questions
2. Includes the retrieved document chunks as context with source identifiers
3. Presents the user's question
4. Instructs the model to cite sources in its answer

## Limitations

TinyLlama (1.1B parameters) is a small model chosen for local execution feasibility. It can produce reasonable answers for straightforward questions but may struggle with complex multi-hop reasoning (e.g., "Is service X covered in jurisdiction Y if the patient has condition Z?"). Upgrading to a larger model or using an API-based model is a straightforward configuration change.

## Connections

The generation chain is the user-facing output of the [[rag-architecture]]. Its answer quality depends on the [[retrieval-strategy]] providing relevant context and the prompt design effectively focusing the model's attention. The [[eval-framework]] measures end-to-end quality. The chain serves [[revenue-cycle-management]] teams by converting complex [[coverage-determination]] and [[billing-and-coding]] rules into accessible answers.
