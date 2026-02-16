"""Streamlit app for testing Medicare RAG embedding search.

Launch:
    streamlit run app.py
"""

from __future__ import annotations

import time
from typing import Any

import streamlit as st

from medicare_rag.config import COLLECTION_NAME, EMBEDDING_MODEL
from medicare_rag.index.embed import get_embeddings
from medicare_rag.index.store import get_or_create_chroma

st.set_page_config(
    page_title="Medicare Embedding Search",
    page_icon="🔍",
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


def _get_collection_meta(store) -> dict[str, Any]:
    """Gather metadata stats from the Chroma collection for filter options."""
    collection = store._collection
    count = collection.count()
    if count == 0:
        return {"count": 0, "sources": [], "manuals": [], "jurisdictions": []}

    all_meta = collection.get(include=["metadatas"])
    metadatas = all_meta.get("metadatas") or []

    sources: set[str] = set()
    manuals: set[str] = set()
    jurisdictions: set[str] = set()

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
        "count": count,
        "sources": sorted(sources),
        "manuals": sorted(manuals),
        "jurisdictions": sorted(jurisdictions),
    }


# ---------------------------------------------------------------------------
# Quick-check bubble questions
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
# CSS for bubble buttons and result cards
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<style>
/* Quick-question bubbles */
div.bubble-container {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1rem;
}
div.bubble-container button {
    background: #f0f2f6;
    border: 1px solid #d1d5db;
    border-radius: 1.25rem;
    padding: 0.4rem 1rem;
    font-size: 0.85rem;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s;
}
div.bubble-container button:hover {
    background: #e0e7ff;
    border-color: #6366f1;
}

/* Result card styling */
div.result-card {
    border: 1px solid #e5e7eb;
    border-radius: 0.75rem;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    background: #fafbfc;
}
div.result-card:hover {
    border-color: #6366f1;
    box-shadow: 0 1px 4px rgba(99,102,241,0.12);
}
div.result-card .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
div.result-card .score-badge {
    background: #e0e7ff;
    color: #4338ca;
    padding: 0.15rem 0.6rem;
    border-radius: 0.75rem;
    font-size: 0.8rem;
    font-weight: 600;
}
div.result-card .meta-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin-bottom: 0.5rem;
}
div.result-card .meta-pill {
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    border-radius: 0.5rem;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    color: #374151;
}
div.result-card .content-preview {
    font-size: 0.9rem;
    color: #1f2937;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
}
</style>
"""

# ---------------------------------------------------------------------------
# Helper: run similarity search
# ---------------------------------------------------------------------------

def _run_search(
    store,
    query: str,
    k: int,
    metadata_filter: dict | None,
    score_threshold: float | None,
) -> list[tuple[Any, float]]:
    """Run similarity_search_with_score and return results."""
    kwargs: dict[str, Any] = {"k": k}
    if metadata_filter:
        kwargs["filter"] = metadata_filter

    results = store.similarity_search_with_score(query, **kwargs)

    if score_threshold is not None:
        results = [(doc, score) for doc, score in results if score <= score_threshold]

    return results


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
    return parts or None


def _render_result_card(rank: int, doc: Any, score: float, show_full: bool) -> None:
    """Render a single search result as a styled card."""
    meta = doc.metadata or {}
    content = doc.page_content or ""

    source_label = meta.get("source", "unknown").upper()
    doc_id = meta.get("doc_id", "")
    title = meta.get("title", "")

    header_text = title if title else doc_id if doc_id else f"Result {rank}"

    # Build pill metadata
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
            pills_html += f'<span class="meta-pill"><b>{label}:</b> {val}</span>'

    preview = content if show_full else (content[:500] + "..." if len(content) > 500 else content)

    card_html = f"""
    <div class="result-card">
        <div class="card-header">
            <b>#{rank} &mdash; {_escape(header_text[:120])}</b>
            <span class="score-badge">dist: {score:.4f}</span>
        </div>
        <div class="meta-pills">{pills_html}</div>
        <div class="content-preview">{_escape(preview)}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _escape(text: str) -> str:
    """Basic HTML entity escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # ---- Sidebar ----
    with st.sidebar:
        st.header("Search Settings")

        store = _load_store()
        meta_info = _get_collection_meta(store)
        doc_count = meta_info["count"]

        st.caption(f"Collection: **{COLLECTION_NAME}**")
        st.caption(f"Documents indexed: **{doc_count:,}**")
        st.caption(f"Embedding model: `{EMBEDDING_MODEL}`")

        st.divider()

        if doc_count == 0:
            st.warning("Index is empty. Run ingestion first (`scripts/ingest_all.py`).")

        # -- Filters --
        st.subheader("Filters")

        source_options = ["All"] + [s.upper() for s in meta_info["sources"]]
        source_filter = st.selectbox("Source", source_options, index=0)

        manual_options = ["All"] + meta_info["manuals"]
        manual_filter = st.selectbox("Manual", manual_options, index=0)

        jurisdiction_options = ["All"] + meta_info["jurisdictions"]
        jurisdiction_filter = st.selectbox("Jurisdiction", jurisdiction_options, index=0)

        st.divider()

        # -- Advanced Options --
        st.subheader("Advanced Options")

        k = st.slider("Top-K results", min_value=1, max_value=50, value=10, step=1)

        use_threshold = st.checkbox("Apply distance threshold", value=False)
        score_threshold: float | None = None
        if use_threshold:
            score_threshold = st.slider(
                "Max distance (lower = more similar)",
                min_value=0.0,
                max_value=2.0,
                value=1.0,
                step=0.05,
            )

        show_full_content = st.checkbox("Show full chunk content", value=False)

    # ---- Main Area ----
    st.title("Medicare Embedding Search")
    st.markdown("Search your indexed Medicare documents by semantic similarity. Use the sidebar to filter and tune results.")

    # -- Quick-check bubbles --
    st.markdown("##### Quick checks")
    bubble_cols = st.columns(4)
    selected_bubble: str | None = None
    for i, q in enumerate(QUICK_QUESTIONS):
        col = bubble_cols[i % 4]
        if col.button(q, key=f"bubble_{i}", use_container_width=True):
            selected_bubble = q

    st.divider()

    # -- Search bar --
    query = st.text_input(
        "Search query",
        value=selected_bubble or "",
        placeholder="Type your search query here...",
        key="search_input",
    )

    if query and doc_count > 0:
        metadata_filter = _build_metadata_filter(
            source_filter or "All",
            manual_filter or "All",
            jurisdiction_filter or "All",
        )

        with st.spinner("Searching embeddings..."):
            t0 = time.perf_counter()
            results = _run_search(store, query, k, metadata_filter, score_threshold)
            elapsed = time.perf_counter() - t0

        st.markdown(f"**{len(results)}** results in **{elapsed:.3f}s**")

        if not results:
            st.info("No results matched your query and filters. Try broadening your search or adjusting filters.")
        else:
            for rank, (doc, score) in enumerate(results, start=1):
                _render_result_card(rank, doc, score, show_full_content)

    elif query and doc_count == 0:
        st.error("Cannot search: the index is empty. Please run ingestion first.")


if __name__ == "__main__":
    main()
