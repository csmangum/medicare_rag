"""Streamlit app for Medicare RAG search and Q&A.

Supports:
  - Hybrid retrieval (semantic + BM25) with LCD-aware query expansion
  - Raw semantic search with distance scores
  - Optional RAG answers via local LLM

Launch:
    streamlit run app.py
"""

from __future__ import annotations

import html
import re
import time
from typing import Any

import streamlit as st

from medicare_rag.config import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
)
from medicare_rag.index.embed import get_embeddings
from medicare_rag.index.store import (
    GET_META_BATCH_SIZE,
    get_or_create_chroma,
    get_raw_collection,
)
from medicare_rag.query.retriever import get_retriever

try:
    from medicare_rag.query.chain import run_rag as _run_rag

    _RAG_AVAILABLE = True
except ImportError:
    _run_rag = None  # type: ignore[assignment]
    _RAG_AVAILABLE = False

st.set_page_config(
    page_title="Medicare RAG",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Cached resources
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner="Loading embedding model...")
def _load_embeddings():
    return get_embeddings()


@st.cache_resource(show_spinner="Connecting to ChromaDB...")
def _load_store():
    emb = _load_embeddings()
    return get_or_create_chroma(emb)


def _run_hybrid_search(
    store,
    embeddings,
    query: str,
    k: int,
    metadata_filter: dict | None,
) -> list[Any]:
    """Run retrieval via get_retriever (Hybrid or LCDAware)."""
    retriever = get_retriever(
        k=k, metadata_filter=metadata_filter, embeddings=embeddings, store=store
    )
    return retriever.invoke(query)


@st.cache_data(show_spinner=False, ttl=300)
def _get_collection_meta(_store) -> dict[str, Any]:
    """Gather aggregated metadata stats from the Chroma collection for filter widgets.

    This function is intentionally cached with ``st.cache_data`` and a short TTL
    (300 seconds). The TTL-based invalidation keeps the per-request overhead low
    while still allowing updates to the underlying collection to be picked up
    periodically without manual cache clears.

    Metadata is read in batches of size ``GET_META_BATCH_SIZE`` via repeated
    ``collection.get(...)`` calls instead of a single unbounded query. This
    batching avoids hitting SQLite / Chroma limits on query size and reduces the
    chance of database errors when the collection grows large.

    The ``_store`` parameter is the cached Chroma store handle obtained from
    ``_load_store()``. The leading underscore indicates that it is an internal
    implementation detail (not user input). Streamlit excludes underscore-prefixed
    parameters from the cache key hashing, so changes to the underlying store do
    not directly invalidate this cache entry; instead, the short TTL controls how
    frequently metadata is refreshed.
    """
    collection = get_raw_collection(_store)
    if collection.count() == 0:
        return {"count": 0, "sources": [], "manuals": [], "jurisdictions": []}

    sources: set[str] = set()
    manuals: set[str] = set()
    jurisdictions: set[str] = set()
    total_seen = 0

    offset = 0
    while True:
        batch = collection.get(
            include=["metadatas"],
            limit=GET_META_BATCH_SIZE,
            offset=offset,
        )
        metadatas = batch.get("metadatas") or []
        if not metadatas:
            break
        offset += len(metadatas)
        total_seen += len(metadatas)
        for m in metadatas:
            if not m:
                continue
            if m.get("source"):
                sources.add(str(m["source"]))
            if m.get("manual"):
                manuals.add(str(m["manual"]))
            if m.get("jurisdiction"):
                jurisdictions.add(str(m["jurisdiction"]))

    return {
        "count": total_seen,
        "sources": sorted(sources),
        "manuals": sorted(manuals),
        "jurisdictions": sorted(jurisdictions),
    }


# ---------------------------------------------------------------------------
# Search mode constants
# ---------------------------------------------------------------------------
_MODE_HYBRID = "Hybrid (recommended)"
_MODE_RAW = "Raw semantic"

# ---------------------------------------------------------------------------
# Quick-check questions
# ---------------------------------------------------------------------------
QUICK_QUESTIONS: list[str] = [
    "What is Medicare timely filing?",
    "How does LCD coverage determination work?",
    "Explain modifier 59 usage",
    "What are HCPCS Level II codes?",
    "ICD-10-CM coding guidelines overview",
    "Medicare claims appeal process",
    "What is a National Coverage Determination?",
    "Outpatient prospective payment system basics",
]

# ---------------------------------------------------------------------------
# CSS: clean, modern design (light theme)
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<style>
/* Main area */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1100px;
}

/* Result card */
div.result-card {
    border: 1px solid #e2e8f0;
    border-radius: 0.5rem;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
    background: #f8fafc;
    transition: border-color 0.2s, box-shadow 0.2s;
}
div.result-card:hover {
    border-color: #6366f1;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.08);
}
div.result-card .card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
    margin-bottom: 0.75rem;
}
div.result-card .card-title {
    font-weight: 600;
    font-size: 0.95rem;
}
div.result-card .score-badge {
    background: #eef2ff;
    color: #4338ca;
    padding: 0.2rem 0.65rem;
    border-radius: 0.5rem;
    font-size: 0.75rem;
    font-weight: 500;
    flex-shrink: 0;
}
div.result-card .meta-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 0.75rem;
}
div.result-card .meta-pill {
    background: #f1f5f9;
    border: 1px solid #e2e8f0;
    border-radius: 0.35rem;
    padding: 0.15rem 0.5rem;
    font-size: 0.72rem;
    color: #64748b;
}
div.result-card .content-preview {
    font-size: 0.9rem;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
}

/* Quick-question chips */
.stButton > button[kind="secondary"] {
    border-radius: 0.5rem !important;
    font-size: 0.85rem !important;
}
</style>
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape(text: str) -> str:
    """HTML entity escaping for safe display in markdown."""
    return html.escape(text, quote=True)


def _build_metadata_filter(
    source_filter: str,
    manual_filter: str,
    jurisdiction_filter: str,
) -> dict | None:
    """Build a Chroma where-clause dict from sidebar selections."""
    parts: dict[str, str] = {}
    if source_filter and source_filter != "All":
        parts["source"] = source_filter.lower()
    if manual_filter and manual_filter != "All":
        parts["manual"] = manual_filter
    if jurisdiction_filter and jurisdiction_filter != "All":
        parts["jurisdiction"] = jurisdiction_filter

    if len(parts) > 1:
        return {"$and": [{k: v} for k, v in parts.items()]}

    return parts or None


def _get_embedding_dimensions(store, embeddings) -> tuple[int | None, int]:
    """Return (collection_embedding_dim, current_model_dim)."""
    collection = get_raw_collection(store)
    model_dim: int = len(embeddings.embed_query("x"))
    try:
        sample = collection.get(limit=1, include=["embeddings"])
        embs = sample.get("embeddings") if sample else None
        if embs and len(embs) > 0 and embs[0] is not None:
            emb = embs[0]
            coll_dim = int(getattr(emb, "size", len(emb)))
            return (coll_dim, model_dim)
    except Exception:
        pass
    return (None, model_dim)


def _run_raw_search(
    store,
    query: str,
    k: int,
    metadata_filter: dict | None,
    score_threshold: float | None,
) -> list[tuple[Any, float]]:
    """Run raw similarity_search_with_score for distance display."""
    kwargs: dict[str, Any] = {"k": k}
    if metadata_filter:
        kwargs["filter"] = metadata_filter

    results = store.similarity_search_with_score(query, **kwargs)

    if score_threshold is not None:
        results = [(doc, score) for doc, score in results if score <= score_threshold]

    return results


def _render_result_card(
    rank: int, doc: Any, score: float | None, show_full: bool
) -> None:
    """Render a single search result as a styled card."""
    meta = doc.metadata or {}
    content = doc.page_content or ""

    source_label = meta.get("source", "unknown").upper()
    doc_id = meta.get("doc_id", "")
    title = meta.get("title", "")

    header_text = title if title else doc_id if doc_id else f"Result {rank}"

    pills_html = ""
    pill_keys = [
        ("source", source_label),
        ("manual", meta.get("manual")),
        ("chapter", meta.get("chapter")),
        ("jurisdiction", meta.get("jurisdiction")),
        ("effective_date", meta.get("effective_date")),
    ]
    for label, val in pill_keys:
        if val:
            pills_html += f'<span class="meta-pill"><b>{label}:</b> {_escape(str(val))}</span>'

    preview = (
        content
        if show_full
        else (content[:500] + "..." if len(content) > 500 else content)
    )

    score_badge = ""
    if score is not None:
        score_badge = f'<span class="score-badge">dist: {score:.4f}</span>'

    card_html = f"""
    <div class="result-card">
        <div class="card-header">
            <span class="card-title">#{rank} &mdash; {_escape(header_text[:120])}</span>
            {score_badge}
        </div>
        <div class="meta-pills">{pills_html}</div>
        <div class="content-preview">{_escape(preview)}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main() -> None:
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # ---- Sidebar ----
    with st.sidebar:
        st.header("🔧 Settings")

        store = _load_store()
        embeddings = _load_embeddings()
        meta_info = _get_collection_meta(store)
        doc_count = meta_info["count"]

        coll_dim, model_dim = _get_embedding_dimensions(store, embeddings)
        dimension_mismatch = (
            doc_count > 0 and coll_dim is not None and coll_dim != model_dim
        )

        st.caption(f"**Collection:** `{COLLECTION_NAME}`")
        st.caption(f"**Documents:** {doc_count:,}")
        st.caption(f"**Model:** `{EMBEDDING_MODEL}`")

        st.divider()

        if doc_count == 0:
            st.warning("Index is empty. Run `scripts/ingest_all.py` first.")
        elif dimension_mismatch:
            st.error(f"Dimension mismatch: index={coll_dim}, model={model_dim}")

        # Filters
        st.subheader("Filters")

        source_options = ["All"] + [s.upper() for s in meta_info["sources"]]
        source_filter = st.selectbox("Source", source_options, index=0)

        manual_options = ["All"] + meta_info["manuals"]
        manual_filter = st.selectbox("Manual", manual_options, index=0)

        jurisdiction_options = ["All"] + meta_info["jurisdictions"]
        jurisdiction_filter = st.selectbox("Jurisdiction", jurisdiction_options, index=0)

        st.divider()
        st.subheader("Options")

        k = st.slider("Top-K results", min_value=1, max_value=50, value=10, step=1)

        search_mode = st.radio(
            "Search mode",
            [_MODE_HYBRID, _MODE_RAW],
            help="Hybrid uses semantic + BM25 with LCD-aware expansion. Raw shows distance scores.",
        )

        use_threshold: bool = False
        score_threshold: float | None = None
        if search_mode == _MODE_RAW:
            use_threshold = st.checkbox("Apply distance threshold", value=False)
            if use_threshold:
                score_threshold = st.slider(
                    "Max distance (lower = more similar)",
                    min_value=0.0,
                    max_value=2.0,
                    value=1.0,
                    step=0.05,
                )

        show_full_content = st.checkbox("Show full chunk content", value=False)

    metadata_filter = _build_metadata_filter(
        source_filter or "All",
        manual_filter or "All",
        jurisdiction_filter or "All",
    )

    # ---- Main area ----
    st.title("Medicare RAG")
    st.markdown(
        "Search Medicare Revenue Cycle documents using hybrid retrieval (semantic + keyword). "
        "Ask questions and get cited answers."
    )

    # Tabs: Search | RAG Answer
    tab_search, tab_rag = st.tabs(["🔍 Search", "💬 RAG Answer"])

    # ---- Search tab ----
    with tab_search:
        st.markdown("#### Quick questions")
        bubble_cols = st.columns(4)
        for i, q in enumerate(QUICK_QUESTIONS):
            col = bubble_cols[i % 4]
            if col.button(q, key=f"bubble_{i}", use_container_width=True):
                st.session_state.search_input = q

        st.divider()

        query = st.text_input(
            "Search query",
            placeholder="Type your Medicare RCM question...",
            key="search_input",
        )

        if query and dimension_mismatch:
            st.error(
                f"**Embedding dimension mismatch.** Index expects **{coll_dim}**-dim vectors, "
                f"model produces **{model_dim}**. Update `EMBEDDING_MODEL` in `.env` or re-ingest."
            )
        elif query and doc_count > 0:
            try:
                if search_mode == _MODE_HYBRID:
                    with st.spinner("Searching (hybrid semantic + keyword)..."):
                        t0 = time.perf_counter()
                        docs = _run_hybrid_search(store, embeddings, query, k, metadata_filter)
                        elapsed = time.perf_counter() - t0

                    st.markdown(f"**{len(docs)}** results in **{elapsed:.3f}s**")

                    if not docs:
                        st.info(
                            "No results matched. Try broadening your search or adjusting filters."
                        )
                    else:
                        for rank, doc in enumerate(docs, start=1):
                            _render_result_card(rank, doc, None, show_full_content)
                else:
                    with st.spinner("Searching embeddings..."):
                        t0 = time.perf_counter()
                        results = _run_raw_search(
                            store, query, k, metadata_filter, score_threshold
                        )
                        elapsed = time.perf_counter() - t0

                    st.markdown(f"**{len(results)}** results in **{elapsed:.3f}s**")

                    if not results:
                        st.info(
                            "No results matched. Try broadening your search or adjusting filters."
                        )
                    else:
                        for rank, (doc, score) in enumerate(results, start=1):
                            _render_result_card(
                                rank, doc, score, show_full_content
                            )
            except Exception as e:
                err_msg = str(e)
                match = re.search(
                    r"dimension of (\d+), got (\d+)", err_msg, re.IGNORECASE
                )
                if match:
                    expected_dim, got_dim = int(match.group(1)), int(match.group(2))
                    st.error(
                        f"**Dimension mismatch.** Index expects **{expected_dim}**, "
                        f"model produces **{got_dim}**. Fix `EMBEDDING_MODEL` or re-ingest."
                    )
                else:
                    raise

        elif query and doc_count == 0:
            st.error("Index is empty. Run `scripts/ingest_all.py` first.")

    # ---- RAG tab ----
    with tab_rag:
        if "rag_result" not in st.session_state:
            st.session_state.rag_result = None  # (answer, source_docs, elapsed) or None

        rag_query = st.text_input(
            "Ask a question",
            placeholder="e.g. What is Medicare timely filing?",
            key="rag_input",
        )

        if rag_query and doc_count > 0 and not dimension_mismatch:
            if st.button("Get answer", type="primary"):
                if not _RAG_AVAILABLE:
                    st.error(
                        "RAG dependencies not installed. "
                        "Run `pip install -e .` to install `langchain-huggingface`."
                    )
                    st.session_state.rag_result = None
                else:
                    try:
                        with st.spinner("Retrieving and generating answer..."):
                            t0 = time.perf_counter()
                            answer, source_docs = _run_rag(
                                rag_query,
                                retriever=None,
                                k=k,
                                metadata_filter=metadata_filter,
                            )
                            elapsed = time.perf_counter() - t0
                        st.session_state.rag_result = (answer, source_docs, elapsed)
                    except (ValueError, RuntimeError, OSError, ImportError) as e:
                        st.error(f"RAG failed: {e}")
                        st.session_state.rag_result = None

            if st.session_state.rag_result is not None:
                answer, source_docs, elapsed = st.session_state.rag_result
                st.markdown("#### Answer")
                st.markdown(answer)
                st.caption(f"Generated in **{elapsed:.2f}s**")

                st.markdown("#### Sources")
                for rank, doc in enumerate(source_docs, start=1):
                    _render_result_card(rank, doc, None, show_full_content)

        elif rag_query and (doc_count == 0 or dimension_mismatch):
            st.error("Index is empty or has dimension mismatch. Fix before using RAG.")


if __name__ == "__main__":
    main()
