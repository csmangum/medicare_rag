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


# ---------------------------------------------------------------------------
# Automated answer quality heuristics
# ---------------------------------------------------------------------------

def _strip_prompt_artifacts(answer: str) -> str:
    """Remove chat-template markers that leak into raw LLM output."""
    import re
    # Strip everything before the last <|assistant|> tag (keeps only the answer)
    parts = re.split(r"<\|assistant\|>\s*", answer)
    cleaned = parts[-1] if len(parts) > 1 else answer
    # Remove stray <|...|> tokens
    cleaned = re.sub(r"<\|[^|]+\|>", "", cleaned)
    return cleaned.strip()


def _count_citations(answer: str) -> list[int]:
    """Return list of citation numbers found (e.g. [1], [2])."""
    import re
    return sorted(set(int(m) for m in re.findall(r"\[(\d+)\]", answer)))




def _repetition_ratio(answer: str) -> float:
    """Ratio of unique sentences to total sentences.  Lower = more repetitive."""
    sentences = [s.strip() for s in answer.replace("\n", " ").split(".") if s.strip()]
    if len(sentences) <= 1:
        return 1.0
    return len(set(sentences)) / len(sentences)


def _answer_quality_metrics(
    answer: str,
    expected_keywords: list[str] | None,
    n_source_docs: int,
) -> dict:
    """Compute automated heuristic quality metrics for a single answer."""
    from validate_and_eval import _keyword_fraction

    citations = _count_citations(answer)
    return {
        "answer_length": len(answer),
        "citation_count": len(citations),
        "citations_found": citations,
        "cites_any_source": len(citations) > 0,
        "cites_all_sources": citations == list(range(1, n_source_docs + 1)) if n_source_docs > 0 else False,
        "keyword_coverage": round(_keyword_fraction(answer, expected_keywords or []), 3),
        "repetition_ratio": round(_repetition_ratio(answer), 3),
    }


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

    all_quality: list[dict] = []

    for i, q in enumerate(questions, start=1):
        qid = q.get("id", "?")
        query = q.get("query", "")
        category = q.get("category", "")
        difficulty = q.get("difficulty", "")
        description = q.get("description", "")
        expected_keywords = q.get("expected_keywords")
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

        # Clean answer and compute quality heuristics
        clean_answer = _strip_prompt_artifacts(answer)
        quality = _answer_quality_metrics(clean_answer, expected_keywords, len(source_docs))
        quality["id"] = qid
        all_quality.append(quality)

        lines.append("### Answer")
        lines.append("")
        lines.append(clean_answer)
        lines.append("")
        lines.append("### Quality heuristics")
        lines.append("")
        lines.append(
            f"- Keywords covered: {quality['keyword_coverage']:.0%} "
            f"| Citations: {quality['citation_count']} "
            f"| Repetition ratio: {quality['repetition_ratio']:.2f} "
            f"| Length: {quality['answer_length']}"
        )
        lines.append("")
        lines.append("### Cited sources")
        lines.append("")
        for j, doc in enumerate(source_docs, start=1):
            meta_str = _format_source_meta(doc.metadata)
            lines.append(f"- **[{j}]** {meta_str}")
            snippet = (doc.page_content or "")[:200].replace("\n", " ")
            if len(doc.page_content or "") > 200:
                snippet += "..."
            lines.append(f"  - {snippet}")
            lines.append("")
        lines.append("---")
        lines.append("")
        logger.info("Processed %d/%d: %s", i, len(questions), qid)

    # ---- Summary section ----
    if all_quality:
        n_q = len(all_quality)
        avg_kw = sum(q["keyword_coverage"] for q in all_quality) / n_q
        avg_rep = sum(q["repetition_ratio"] for q in all_quality) / n_q
        avg_cit = sum(q["citation_count"] for q in all_quality) / n_q
        pct_citing = sum(1 for q in all_quality if q["cites_any_source"]) / n_q
        avg_len = sum(q["answer_length"] for q in all_quality) / n_q

        lines.insert(6, "## Answer Quality Summary")
        lines.insert(7, "")
        lines.insert(8, "| Metric | Value |")
        lines.insert(9, "|--------|-------|")
        lines.insert(10, f"| Questions | {n_q} |")
        lines.insert(11, f"| Avg keyword coverage | {avg_kw:.1%} |")
        lines.insert(12, f"| Avg citation count | {avg_cit:.1f} |")
        lines.insert(13, f"| % answers with citations | {pct_citing:.0%} |")
        lines.insert(14, f"| Avg repetition ratio | {avg_rep:.2f} (1.0 = no repetition) |")
        lines.insert(15, f"| Avg answer length | {avg_len:.0f} chars |")
        lines.insert(16, "")
        lines.insert(17, "---")
        lines.insert(18, "")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote report to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
