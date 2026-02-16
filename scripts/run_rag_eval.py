#!/usr/bin/env python3
"""Run the full RAG chain on the eval question set and write a report for manual assessment.

Loads eval_questions.json, runs each question through the query chain (retriever + LLM),
and writes a markdown report with question, answer, and cited source metadata. Use the
report to manually assess answer quality and citation accuracy.

Usage:
  python scripts/run_rag_eval.py
  python scripts/run_rag_eval.py --eval-file scripts/eval_questions.json --out data/rag_eval_report.md
  python scripts/run_rag_eval.py -k 8
"""
import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EVAL_FILE = _SCRIPT_DIR / "eval_questions.json"

SOURCE_META_KEYS = ("source", "manual", "chapter", "doc_id", "jurisdiction", "title")
EVAL_QUESTION_EXTRA_KEYS = ("category", "difficulty", "description")


def _format_source_meta(doc_meta: dict) -> str:
    parts = []
    for key in SOURCE_META_KEYS:
        if key in doc_meta and doc_meta[key] is not None:
            parts.append(f"{key}={doc_meta[key]}")
    return " ".join(parts) if parts else "(no metadata)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run full RAG chain on eval questions and write report for manual assessment."
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_FILE,
        help="Path to eval_questions.json (default: scripts/eval_questions.json).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output report path (default: DATA_DIR/rag_eval_report.md).",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=8,
        help="Number of chunks to retrieve per question (default: 8).",
    )
    args = parser.parse_args()

    if not args.eval_file.exists():
        logger.error("Eval file not found: %s", args.eval_file)
        return 1

    with open(args.eval_file, encoding="utf-8") as f:
        questions = json.load(f)
    if not questions:
        logger.warning("Eval file is empty")
        return 0

    from medicare_rag.config import CHROMA_DIR, COLLECTION_NAME, DATA_DIR
    from medicare_rag.index import get_embeddings, get_or_create_chroma
    from medicare_rag.query.retriever import get_retriever

    out_path = args.out if args.out is not None else DATA_DIR / "rag_eval_report.md"

    if not CHROMA_DIR.exists():
        logger.error("Chroma index not found at %s. Run ingestion first.", CHROMA_DIR)
        return 1

    try:
        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        if store._collection.count() == 0:
            logger.error("Collection %s is empty. Run ingestion first.", COLLECTION_NAME)
            return 1
        retriever = get_retriever(k=args.k)
    except Exception as e:
        logger.error("Failed to load index/retriever: %s", e)
        return 1

    lines = [
        "# RAG Eval Report (manual assessment)",
        "",
        f"Eval file: `{args.eval_file}`",
        f"Retriever k: {args.k}",
        "",
        "---",
        "",
    ]

    # Build RAG chain once before loop to avoid reloading LLM for every question
    from medicare_rag.query.chain import build_rag_chain
    try:
        rag_chain = build_rag_chain(retriever=retriever, k=args.k)
    except Exception as e:
        logger.error("Failed to build RAG chain: %s", e)
        rag_chain = None

    for i, q in enumerate(questions, start=1):
        qid = q.get("id", "?")
        query = q.get("query", "")
        category = q.get("category", "")
        difficulty = q.get("difficulty", "")
        description = q.get("description", "")
        lines.append(f"## {i}. [{qid}] {query}")
        lines.append("")
        meta_parts = []
        if category:
            meta_parts.append(f"Category: {category}")
        if difficulty:
            meta_parts.append(f"Difficulty: {difficulty}")
        if description:
            meta_parts.append(f"Description: {description}")
        if meta_parts:
            lines.append(f"> {' | '.join(meta_parts)}")
            lines.append("")
        try:
            if rag_chain is None:
                raise RuntimeError("RAG chain not initialized")
            result = rag_chain({"question": query})
            answer = result["answer"]
            source_docs = result["source_documents"]
        except Exception as e:
            answer = f"LLM not configured or error: {e}"
            # Fallback: retrieve docs only when LLM fails
            source_docs = retriever.invoke(query)
        lines.append("### Answer")
        lines.append("")
        lines.append(answer)
        lines.append("")
        lines.append("### Cited sources")
        lines.append("")
        for j, doc in enumerate(source_docs, start=1):
            meta_str = _format_source_meta(doc.metadata)
            lines.append(f"- **[{j}]** {meta_str}")
            snippet = (doc.page_content or "")[:200].replace("\n", " ")
            if len((doc.page_content or "")) > 200:
                snippet += "..."
            lines.append(f"  - {snippet}")
            lines.append("")
        lines.append("---")
        lines.append("")
        logger.info("Processed %d/%d: %s", i, len(questions), qid)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote report to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
