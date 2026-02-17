"""Streamlit app for testing Medicare RAG embedding search.

Launch:
    streamlit run app.py
"""

from __future__ import annotations

import html
import re
import time
from typing import Any

import streamlit as st

from medicare_rag.config import COLLECTION_NAME, EMBEDDING_MODEL
from medicare_rag.index.embed import get_embeddings
from medicare_rag.index.store import (
    GET_META_BATCH_SIZE,
    get_or_create_chroma,
    get_raw_collection,
)

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


@st.cache_data(show_spinner=False, ttl=300)
def _get_collection_meta(_store) -> dict[str, Any]:
    """Gather metadata stats from the Chroma collection for filter options.

    Cached for 5 minutes to avoid reloading all metadata on every rerun.
    Cache will automatically invalidate after TTL expires, allowing new documents
    to appear in filters.
    Fetches metadata in batches to avoid ChromaDB/SQLite "too many SQL variables" error.

    Args:
        _store: Chroma vector store. Underscore prefix follows Streamlit convention
                to exclude this parameter from the cache key (only TTL-based invalidation).
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
# CSS for result cards
# ---------------------------------------------------------------------------
_CUSTOM_CSS = """
<style>
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
        # Convert back to lowercase since ChromaDB stores lowercase source values
        parts["source"] = source_filter.lower()
    if manual_filter and manual_filter != "All":
        parts["manual"] = manual_filter
    if jurisdiction_filter and jurisdiction_filter != "All":
        parts["jurisdiction"] = jurisdiction_filter

    # ChromaDB requires exactly one key in a where-clause dict.
    # If we have multiple filters, wrap them in $and operator.
    if len(parts) > 1:
        return {"$and": [{k: v} for k, v in parts.items()]}

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
            pills_html += f'<span class="meta-pill"><b>{label}:</b> {_escape(str(val))}</span>'

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
    """HTML entity escaping for safe display in markdown."""
    return html.escape(text, quote=True)


def _get_embedding_dimensions(store, embeddings) -> tuple[int | None, int]:
    """Return (collection_embedding_dim, current_model_dim).
    collection_embedding_dim is None if the collection is empty.
    """
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


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    st.markdown(_CUSTOM_CSS, unsafe_allow_html=True)

    # ---- Sidebar ----
    with st.sidebar:
        st.header("Search Settings")

        store = _load_store()
        embeddings = _load_embeddings()
        meta_info = _get_collection_meta(store)
        doc_count = meta_info["count"]

        coll_dim, model_dim = _get_embedding_dimensions(store, embeddings)
        dimension_mismatch = (
            doc_count > 0
            and coll_dim is not None
            and coll_dim != model_dim
        )

        st.caption(f"Collection: **{COLLECTION_NAME}**")
        st.caption(f"Documents indexed: **{doc_count:,}**")
        st.caption(f"Embedding model: `{EMBEDDING_MODEL}`")

        st.divider()

        if doc_count == 0:
            st.warning("Index is empty. Run ingestion first (`scripts/ingest_all.py`).")
        elif dimension_mismatch:
            st.error(f"Embedding dimension mismatch: index={coll_dim}, model={model_dim}")

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
    st.markdown(
        "Search your indexed Medicare documents by semantic similarity. "
        "Use the sidebar to filter and tune results."
    )

    # -- Quick-check bubbles --
    st.markdown("##### Quick checks")
    bubble_cols = st.columns(4)
    for i, q in enumerate(QUICK_QUESTIONS):
        col = bubble_cols[i % 4]
        if col.button(q, key=f"bubble_{i}", use_container_width=True):
            st.session_state.search_input = q

    st.divider()

    # -- Search bar --
    query = st.text_input(
        "Search query",
        placeholder="Type your search query here...",
        key="search_input",
    )

    if query and dimension_mismatch:
        st.error(
            "**Embedding dimension mismatch.** The index was built with a different "
            f"embedding model (expected dimension **{coll_dim}**). The current model "
            f"(`{EMBEDDING_MODEL}`) produces dimension **{model_dim}**. Set "
            "`EMBEDDING_MODEL` in `.env` to the model used during ingest "
            f"(e.g. one that outputs {coll_dim}-dim vectors), or re-run ingestion: "
            "`python scripts/ingest_all.py`."
        )
    elif query and doc_count > 0:
        metadata_filter = _build_metadata_filter(
            source_filter or "All",
            manual_filter or "All",
            jurisdiction_filter or "All",
        )

        try:
            with st.spinner("Searching embeddings..."):
                t0 = time.perf_counter()
                results = _run_search(store, query, k, metadata_filter, score_threshold)
                elapsed = time.perf_counter() - t0

            st.markdown(f"**{len(results)}** results in **{elapsed:.3f}s**")

            if not results:
                st.info(
                    "No results matched your query and filters. "
                    "Try broadening your search or adjusting filters."
                )
            else:
                for rank, (doc, score) in enumerate(results, start=1):
                    _render_result_card(rank, doc, score, show_full_content)
        except Exception as e:  # noqa: BLE001
            err_msg = str(e)
            # ChromaDB raises InvalidArgumentError when embedding dimensions don't match
            match = re.search(r"dimension of (\d+), got (\d+)", err_msg, re.IGNORECASE)
            if match:
                expected_dim, got_dim = int(match.group(1)), int(match.group(2))
                st.error(
                    "**Embedding dimension mismatch.** The index was built with a different "
                    f"embedding model (expected dimension **{expected_dim}**). The current model "
                    f"(`{EMBEDDING_MODEL}`) produces dimension **{got_dim}**. Set "
                    "`EMBEDDING_MODEL` in `.env` to the model used during ingest "
                    f"(e.g. one that outputs {expected_dim}-dim vectors), or re-run ingestion: "
                    "`python scripts/ingest_all.py`."
                )
            else:
                raise

    elif query and doc_count == 0:
        st.error("Cannot search: the index is empty. Please run ingestion first.")


if __name__ == "__main__":
    main()
