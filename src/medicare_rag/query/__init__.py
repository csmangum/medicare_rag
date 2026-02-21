"""Retrieval and RAG chain (Phase 4).

Submodules:
    retriever — LCD-aware retriever with query expansion and topic-summary boosting.
    hybrid    — Hybrid retriever (semantic + BM25, RRF, cross-source diversification).
    expand    — Cross-source query expansion and Medicare domain synonym mapping.
    chain     — RAG chain wiring (retriever + local LLM + prompt template).
"""

from medicare_rag.query import expand, hybrid
