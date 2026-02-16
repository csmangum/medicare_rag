#!/usr/bin/env python3
"""Validate the Chroma index and run retrieval evaluation.

Validates: index exists, has documents, required metadata, and similarity_search works.
Eval: runs each question in eval_questions.json through the same retriever used by the
RAG chain (get_retriever), checks for expected keywords/sources in top-k, reports hit
rate and MRR.

Usage:
  python scripts/validate_and_eval.py              # validate + eval
  python scripts/validate_and_eval.py --validate-only
  python scripts/validate_and_eval.py --eval-only
  python scripts/validate_and_eval.py --eval-only -k 10
  python scripts/validate_and_eval.py --eval-only --filter-source iom
  python scripts/validate_and_eval.py --json       # machine-readable metrics
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

# Script dir for eval_questions.json
_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EVAL_PATH = _SCRIPT_DIR / "eval_questions.json"


def _load_store():
    from medicare_rag.index import get_embeddings, get_or_create_chroma
    embeddings = get_embeddings()
    store = get_or_create_chroma(embeddings)
    return store, embeddings


def _load_retriever(k: int, metadata_filter: dict | None = None):
    """Load the same retriever used by the RAG chain (for eval)."""
    from medicare_rag.query.retriever import get_retriever
    return get_retriever(k=k, metadata_filter=metadata_filter)


def validate_index(store) -> bool:
    """Check index exists, has documents, and retrieval works. Returns True if all pass."""
    from medicare_rag.config import CHROMA_DIR, COLLECTION_NAME

    ok = True

    # 1. Chroma dir and collection exist
    if not CHROMA_DIR.exists():
        logger.error("CHROMA_DIR does not exist: %s", CHROMA_DIR)
        return False
    logger.info("CHROMA_DIR exists: %s", CHROMA_DIR)

    collection = store._collection
    try:
        n = collection.count()
    except Exception as e:
        logger.error("collection.count() failed: %s", e)
        return False

    if n == 0:
        logger.error("Collection %s is empty", COLLECTION_NAME)
        return False
    logger.info("Collection %s has %d documents", COLLECTION_NAME, n)

    # 2. Sample document: has required metadata
    try:
        sample = collection.get(limit=1, include=["metadatas", "documents"])
    except Exception as e:
        logger.error("collection.get() failed: %s", e)
        return False

    if not sample or not sample.get("ids"):
        logger.error("No sample document returned")
        return False

    meta = (sample.get("metadatas") or [None])[0] or {}
    for key in ("doc_id", "content_hash"):
        if key not in meta:
            logger.warning("Sample document missing metadata key: %s", key)
            ok = False
    if meta.get("source") and meta["source"] not in ("iom", "mcd", "codes"):
        logger.warning("Unexpected source in sample: %s", meta.get("source"))
    logger.info("Sample doc_id=%s source=%s", meta.get("doc_id"), meta.get("source"))

    # 3. Similarity search works
    try:
        results = store.similarity_search("Medicare coverage", k=2)
    except Exception as e:
        logger.error("similarity_search failed: %s", e)
        return False

    if not results:
        logger.error("similarity_search returned no results")
        return False
    logger.info("similarity_search('Medicare coverage', k=2) returned %d results", len(results))

    return ok


def _question_hit(
    docs: list,
    expected_keywords: list[str] | None,
    expected_sources: list[str] | None,
) -> tuple[bool, int | None, list[str]]:
    """Given top-k docs for a query, return (hit, first_hit_rank_1based, list of source names)."""
    if not docs:
        return False, None, []

    sources_in_k = [d.metadata.get("source") for d in docs if d.metadata.get("source")]

    first_hit_rank = None
    for rank, doc in enumerate(docs, start=1):
        text = (doc.page_content or "").lower()
        source = doc.metadata.get("source")

        keyword_ok = (
            not expected_keywords or any(kw.lower() in text for kw in expected_keywords)
        )
        source_ok = (
            not expected_sources or (source and source in expected_sources)
        )

        if keyword_ok and source_ok:
            first_hit_rank = rank
            break

    hit = first_hit_rank is not None
    return hit, first_hit_rank, sources_in_k


def run_eval(
    eval_path: Path,
    k: int = 5,
    metadata_filter: dict | None = None,
) -> dict:
    """Run eval set using the RAG retriever. Return metrics dict."""
    if not eval_path.exists():
        logger.error("Eval file not found: %s", eval_path)
        return {}

    with open(eval_path, encoding="utf-8") as f:
        questions = json.load(f)

    if not questions:
        logger.warning("Eval file is empty")
        return {"n_questions": 0}

    retriever = _load_retriever(k=k, metadata_filter=metadata_filter)

    results = []
    hits = 0
    reciprocal_ranks = []

    for q in questions:
        qid = q.get("id", "?")
        query = q.get("query", "")
        expected_keywords = q.get("expected_keywords")
        expected_sources = q.get("expected_sources")

        docs = retriever.invoke(query)
        hit, first_rank, sources_in_k = _question_hit(
            docs, expected_keywords, expected_sources
        )
        if hit:
            hits += 1
            reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
        else:
            reciprocal_ranks.append(0.0)

        results.append({
            "id": qid,
            "query": query[:60] + "..." if len(query) > 60 else query,
            "hit": hit,
            "first_hit_rank": first_rank,
            "sources_in_topk": list(dict.fromkeys(sources_in_k)),
        })

    n = len(questions)
    hit_rate = hits / n if n else 0.0
    mrr = sum(reciprocal_ranks) / n if n else 0.0

    metrics = {
        "n_questions": n,
        "k": k,
        "hit_rate": hit_rate,
        "hits": hits,
        "mrr": mrr,
        "results": results,
    }
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the Medicare RAG index and run retrieval evaluation."
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only run index validation (no eval).",
    )
    parser.add_argument(
        "--eval-only",
        action="store_true",
        help="Only run evaluation (skip validation).",
    )
    parser.add_argument(
        "-k",
        type=int,
        default=5,
        metavar="K",
        help="Number of documents to retrieve per query for eval (default: 5).",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_PATH,
        help="Path to eval_questions.json (default: scripts/eval_questions.json).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print eval metrics as JSON to stdout (for piping).",
    )
    parser.add_argument(
        "--filter-source",
        type=str,
        help="Restrict retrieval to this source (e.g. iom, mcd, codes).",
    )
    args = parser.parse_args()

    if args.json:
        logging.getLogger().setLevel(logging.WARNING)

    do_validate = not args.eval_only
    do_eval = not args.validate_only

    metadata_filter = None
    if args.filter_source:
        metadata_filter = {"source": args.filter_source}

    if do_validate:
        try:
            store, _ = _load_store()
        except Exception as e:
            logger.exception("Failed to load store: %s", e)
            return 1
        logger.info("=== Validation ===")
        if not validate_index(store):
            logger.error("Validation failed")
            return 1
        logger.info("Validation passed")

    if do_eval:
        logger.info("=== Evaluation (k=%d) ===", args.k)
        if metadata_filter:
            logger.info("Filter: %s", metadata_filter)
        metrics = run_eval(args.eval_file, k=args.k, metadata_filter=metadata_filter)
        if not metrics:
            return 1

        if args.json:
            out = {k: v for k, v in metrics.items() if k != "results"}
            print(json.dumps(out, indent=2))
        else:
            logger.info(
                "Hit rate: %d/%d (%.2f%%)",
                metrics["hits"],
                metrics["n_questions"],
                metrics["hit_rate"] * 100,
            )
            logger.info("MRR: %.4f", metrics["mrr"])
            for r in metrics["results"]:
                status = "PASS" if r["hit"] else "FAIL"
                rank = f" rank={r['first_hit_rank']}" if r["first_hit_rank"] else ""
                logger.info("  [%s] %s%s", status, r["id"], rank)

    return 0


if __name__ == "__main__":
    sys.exit(main())
