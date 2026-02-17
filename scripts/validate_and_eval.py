#!/usr/bin/env python3
"""Comprehensive search validation and retrieval evaluation for the Medicare RAG index.

Validates the Chroma index thoroughly (structure, metadata, distributions, embeddings)
and runs a rich retrieval evaluation with multiple metrics across categories, difficulty
levels, source types, and query consistency groups.

Metrics produced:
  - Hit Rate (any relevant doc in top-k)
  - MRR (Mean Reciprocal Rank)
  - Precision@k (fraction of top-k that are relevant)
  - NDCG@k (Normalized Discounted Cumulative Gain)
  - Per-source, per-category, per-difficulty breakdowns
  - Consistency score (do rephrased queries retrieve the same documents?)
  - Retrieval latency (p50, p95, p99)

Usage:
  python scripts/validate_and_eval.py              # validate + eval
  python scripts/validate_and_eval.py --validate-only
  python scripts/validate_and_eval.py --eval-only
  python scripts/validate_and_eval.py --eval-only -k 10
  python scripts/validate_and_eval.py --eval-only --filter-source iom
  python scripts/validate_and_eval.py --json       # machine-readable metrics
  python scripts/validate_and_eval.py --eval-only --k-values 1,3,5,10  # multi-k sweep
"""
import argparse
import json
import logging
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_EVAL_PATH = _SCRIPT_DIR / "eval_questions.json"

REQUIRED_METADATA_KEYS = ("doc_id", "content_hash")
EXPECTED_SOURCES = ("iom", "mcd", "codes")


# ---------------------------------------------------------------------------
# Index loading helpers
# ---------------------------------------------------------------------------

def _load_store():
    from medicare_rag.index import get_embeddings, get_or_create_chroma
    embeddings = get_embeddings()
    store = get_or_create_chroma(embeddings)
    return store, embeddings


def _load_retriever(k: int, metadata_filter: dict | None = None):
    from medicare_rag.query.retriever import get_retriever
    return get_retriever(k=k, metadata_filter=metadata_filter)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_index(store) -> dict:
    """Run comprehensive index validation. Returns a dict of results with 'passed' bool."""
    from medicare_rag.config import CHROMA_DIR, COLLECTION_NAME, _REPO_ROOT

    results: dict = {
        "passed": True,
        "checks": [],
        "stats": {},
        "warnings": [],
    }

    def _check(name: str, ok: bool, detail: str = "") -> None:
        results["checks"].append({"name": name, "passed": ok, "detail": detail})
        if not ok:
            results["passed"] = False

    def _warn(msg: str) -> None:
        results["warnings"].append(msg)
        logger.warning(msg)

    # 1. Chroma directory exists
    dir_exists = CHROMA_DIR.exists()
    try:
        rel_path = CHROMA_DIR.relative_to(_REPO_ROOT)
        detail = f"{rel_path} ({CHROMA_DIR})"
    except ValueError:
        detail = str(CHROMA_DIR)
    _check("chroma_dir_exists", dir_exists, detail)
    if not dir_exists:
        return results
    logger.info("CHROMA_DIR exists: %s", CHROMA_DIR)

    # 2. Collection accessible and non-empty
    collection = store._collection
    try:
        doc_count = collection.count()
    except Exception as e:
        _check("collection_accessible", False, str(e))
        return results
    _check("collection_accessible", True, f"collection={COLLECTION_NAME}")
    _check("collection_non_empty", doc_count > 0, f"count={doc_count}")
    if doc_count == 0:
        return results
    logger.info("Collection '%s' has %d documents", COLLECTION_NAME, doc_count)
    results["stats"]["total_documents"] = doc_count

    # 3. Fetch ALL metadata for comprehensive stats (batch to avoid SQL variable limit)
    # Initialize source_counter before conditional block (needed for check #12)
    source_counter: Counter = Counter()
    BATCH_SIZE = 5000
    ids: list = []
    metadatas: list = []
    documents: list = []
    try:
        for offset in range(0, doc_count, BATCH_SIZE):
            batch = collection.get(
                include=["metadatas", "documents"],
                limit=BATCH_SIZE,
                offset=offset,
            )
            if batch and batch.get("ids"):
                ids.extend(batch["ids"])
                metadatas.extend(batch.get("metadatas") or [])
                documents.extend(batch.get("documents") or [])
        all_data = {"ids": ids, "metadatas": metadatas, "documents": documents} if ids else None
    except Exception as e:
        _check("bulk_metadata_fetch", False, str(e))
        _warn(f"Could not fetch all metadata: {e}")
        all_data = None

    if all_data and all_data.get("ids"):
        _check("bulk_metadata_fetch", True, f"fetched {len(ids)} docs")

        # 4. Metadata completeness
        missing_keys_count: dict[str, int] = defaultdict(int)
        has_source_count = 0
        metadata_key_counter: Counter = Counter()

        for meta in metadatas:
            meta = meta or {}
            for key in REQUIRED_METADATA_KEYS:
                if key not in meta:
                    missing_keys_count[key] += 1
            for key in meta:
                metadata_key_counter[key] += 1
            src = meta.get("source")
            if src:
                source_counter[src] += 1
                has_source_count += 1

        for key in REQUIRED_METADATA_KEYS:
            missing = missing_keys_count.get(key, 0)
            pct = (1 - missing / len(ids)) * 100 if ids else 0
            ok = missing == 0
            _check(
                f"metadata_key_{key}",
                ok,
                f"present in {pct:.1f}% of docs ({len(ids) - missing}/{len(ids)})",
            )
            if not ok:
                _warn(f"Metadata key '{key}' missing in {missing}/{len(ids)} documents")

        source_pct = (has_source_count / len(ids) * 100) if ids else 0
        _check(
            "metadata_key_source",
            has_source_count > 0,
            f"present in {source_pct:.1f}% of docs",
        )

        # 5. Source distribution
        results["stats"]["source_distribution"] = dict(source_counter.most_common())
        logger.info("Source distribution: %s", dict(source_counter.most_common()))

        unexpected = [s for s in source_counter if s not in EXPECTED_SOURCES]
        if unexpected:
            _warn(f"Unexpected sources found: {unexpected}")
        for expected_src in EXPECTED_SOURCES:
            present = source_counter.get(expected_src, 0) > 0
            _check(
                f"source_{expected_src}_present",
                present,
                f"count={source_counter.get(expected_src, 0)}",
            )

        # 6. All metadata keys inventory
        results["stats"]["metadata_keys"] = {
            k: v for k, v in metadata_key_counter.most_common()
        }

        # 7. Document content stats
        content_lengths = []
        empty_docs = 0
        for doc_text in documents:
            if not doc_text or not doc_text.strip():
                empty_docs += 1
                content_lengths.append(0)
            else:
                content_lengths.append(len(doc_text))

        _check("no_empty_documents", empty_docs == 0, f"empty={empty_docs}/{len(ids)}")
        if empty_docs:
            _warn(f"{empty_docs} documents have empty content")

        if content_lengths:
            sorted_lengths = sorted(content_lengths)
            results["stats"]["content_length"] = {
                "min": sorted_lengths[0],
                "max": sorted_lengths[-1],
                "median": sorted_lengths[len(sorted_lengths) // 2],
                "mean": sum(sorted_lengths) / len(sorted_lengths),
                "p5": sorted_lengths[int(len(sorted_lengths) * 0.05)],
                "p95": sorted_lengths[int(len(sorted_lengths) * 0.95)],
            }
            logger.info(
                "Content length: min=%d, max=%d, median=%d, mean=%.0f",
                results["stats"]["content_length"]["min"],
                results["stats"]["content_length"]["max"],
                results["stats"]["content_length"]["median"],
                results["stats"]["content_length"]["mean"],
            )

        # 8. Duplicate ID check
        id_counts = Counter(ids)
        duplicates = {k: v for k, v in id_counts.items() if v > 1}
        _check(
            "no_duplicate_ids",
            len(duplicates) == 0,
            f"duplicates={len(duplicates)}" if duplicates else "all unique",
        )
        if duplicates:
            top_dups = dict(Counter(duplicates).most_common(5))
            _warn(f"Duplicate IDs found (top 5): {top_dups}")

        # 9. Content hash uniqueness
        hash_counter = Counter(
            (m or {}).get("content_hash") for m in metadatas if (m or {}).get("content_hash")
        )
        hash_duplicates = {k: v for k, v in hash_counter.items() if v > 1}
        _check(
            "no_duplicate_content_hashes",
            len(hash_duplicates) == 0,
            f"duplicate_hashes={len(hash_duplicates)}" if hash_duplicates else "all unique",
        )
    else:
        _check("bulk_metadata_fetch", False, "no data returned")

    # 10. Similarity search smoke test
    test_queries = [
        ("Medicare coverage", "generic"),
        ("billing claim submission", "claims"),
        ("ICD-10 diagnosis code", "codes"),
    ]
    for query, label in test_queries:
        try:
            search_results = store.similarity_search(query, k=3)
            found = len(search_results)
            _check(
                f"similarity_search_{label}",
                found > 0,
                f"query='{query}' returned {found} results",
            )
        except Exception as e:
            _check(f"similarity_search_{label}", False, str(e))

    # 11. Embedding dimension check
    try:
        sample_embedding = collection.get(
            limit=1, include=["embeddings"]
        )
        # Don't use "if embeddings" - numpy array truth value is ambiguous
        embs = sample_embedding.get("embeddings") if sample_embedding else None
        if embs is not None and len(embs) > 0:
            emb = embs[0]
            dim = int(getattr(emb, "size", len(emb)) if emb is not None else 0)
            results["stats"]["embedding_dimension"] = dim
            _check("embedding_dimension", dim > 0, f"dim={dim}")
            logger.info("Embedding dimension: %d", dim)
        else:
            _check("embedding_dimension", False, "no embeddings returned")
    except Exception as e:
        _check("embedding_dimension", False, str(e))
        _warn(f"Could not check embedding dimension: {e}")

    # 12. Metadata filter retrieval works
    for src in EXPECTED_SOURCES:
        if source_counter.get(src, 0) > 0:
            try:
                filtered = store.similarity_search(
                    "Medicare", k=2, filter={"source": src}
                )
                _check(
                    f"filter_retrieval_{src}",
                    len(filtered) > 0,
                    f"returned {len(filtered)} results",
                )
                for doc in filtered:
                    if doc.metadata.get("source") != src:
                        _check(
                            f"filter_correctness_{src}",
                            False,
                            f"expected source={src}, got {doc.metadata.get('source')}",
                        )
                        break
                else:
                    _check(f"filter_correctness_{src}", True, "all results match filter")
            except Exception as e:
                _check(f"filter_retrieval_{src}", False, str(e))

    # Summary
    passed_count = sum(1 for c in results["checks"] if c["passed"])
    total_count = len(results["checks"])
    results["stats"]["checks_passed"] = passed_count
    results["stats"]["checks_total"] = total_count
    logger.info(
        "Validation: %d/%d checks passed%s",
        passed_count,
        total_count,
        "" if results["passed"] else " [FAILURES DETECTED]",
    )

    return results


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def _dcg(relevances: list[float], k: int) -> float:
    """Compute Discounted Cumulative Gain for the first k items."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += rel / math.log2(i + 2)
    return dcg


def _ndcg(relevances: list[float], k: int) -> float:
    """Compute Normalized DCG@k."""
    dcg = _dcg(relevances, k)
    ideal = _dcg(sorted(relevances, reverse=True), k)
    if ideal == 0:
        return 0.0
    return dcg / ideal


def _keyword_fraction(text: str, expected_keywords: list[str]) -> float:
    """Return fraction of expected keywords found in text (case-insensitive).

    Uses per-keyword matching so that a document mentioning 1 of 4 keywords
    scores 0.25 rather than a binary 1.0.  This avoids inflating relevance
    for broad keyword lists where a single common word like "coverage" would
    previously count as a full keyword match.
    """
    if not expected_keywords:
        return 1.0
    text_lower = text.lower()
    hits = sum(1 for kw in expected_keywords if kw.lower() in text_lower)
    return hits / len(expected_keywords)


def _question_relevance(
    docs: list,
    expected_keywords: list[str] | None,
    expected_sources: list[str] | None,
) -> list[float]:
    """Score each doc on a 0–1 scale combining keyword coverage and source match.

    Scoring:
      keyword_score = fraction of expected_keywords found in doc text (0–1)
      source_match  = 1.0 if doc source in expected_sources, else 0.0
                      (1.0 when no source constraint)

    Final relevance = keyword_score * 0.6 + source_match * 0.4
    This means a doc must match *both* keywords and source well to score
    near 1.0.  A doc matching all keywords but wrong source scores 0.6;
    right source but no keywords scores 0.4; partial keywords + right
    source scores proportionally.

    "Fully relevant" threshold for hit/precision is rel >= 0.8 (was 1.0).
    """
    relevances = []
    for doc in docs:
        text = doc.page_content or ""
        source = doc.metadata.get("source")

        kw_score = _keyword_fraction(text, expected_keywords or [])

        source_match = (
            1.0 if (
                not expected_sources
                or (source and source in expected_sources)
            ) else 0.0
        )

        rel = kw_score * 0.6 + source_match * 0.4
        relevances.append(round(rel, 4))
    return relevances


# Threshold above which a document is considered "relevant" for hit/precision.
RELEVANT_THRESHOLD = 0.8


def _evaluate_question(
    docs: list,
    expected_keywords: list[str] | None,
    expected_sources: list[str] | None,
    k: int,
) -> dict:
    """Evaluate a single question's retrieval results. Returns per-question metrics."""
    relevances = _question_relevance(docs, expected_keywords, expected_sources)

    # Hit: at least one relevant doc (>= threshold) in top-k
    first_hit_rank = None
    for rank, rel in enumerate(relevances, start=1):
        if rel >= RELEVANT_THRESHOLD:
            first_hit_rank = rank
            break

    hit = first_hit_rank is not None
    reciprocal_rank = (1.0 / first_hit_rank) if first_hit_rank else 0.0

    # Precision@k: fraction of top-k that are relevant
    fully_relevant = sum(1 for r in relevances if r >= RELEVANT_THRESHOLD)
    precision_at_k = fully_relevant / k if k > 0 else 0.0

    # Recall@k: fraction of expected sources represented in relevant results
    relevant_sources = set()
    for doc, rel in zip(docs, relevances):
        if rel >= RELEVANT_THRESHOLD:
            src = doc.metadata.get("source")
            if src:
                relevant_sources.add(src)
    if expected_sources:
        recall_at_k = len(relevant_sources & set(expected_sources)) / len(expected_sources)
    else:
        recall_at_k = 1.0 if fully_relevant > 0 else 0.0

    # Partial relevance counts
    partially_relevant = sum(
        1 for r in relevances if 0 < r < RELEVANT_THRESHOLD
    )

    # NDCG@k
    ndcg_at_k = _ndcg(relevances, k)

    # Source diversity in results
    sources_in_results = [
        d.metadata.get("source") for d in docs if d.metadata.get("source")
    ]
    unique_sources = list(dict.fromkeys(sources_in_results))

    return {
        "hit": hit,
        "first_hit_rank": first_hit_rank,
        "reciprocal_rank": reciprocal_rank,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "ndcg_at_k": ndcg_at_k,
        "fully_relevant": fully_relevant,
        "partially_relevant": partially_relevant,
        "sources_in_topk": unique_sources,
        "relevances": relevances,
    }


# ---------------------------------------------------------------------------
# Consistency evaluation
# ---------------------------------------------------------------------------

def _compute_consistency(
    group_results: dict[str, dict],
) -> dict:
    """Given results for a consistency group, compute overlap metrics.

    Each entry in group_results maps question_id -> {"doc_ids": list[str], ...}
    """
    if len(group_results) < 2:
        return {
            "score": 1.0,
            "detail": "single question in group",
            "questions": list(group_results.keys()),
        }

    ids_list = list(group_results.values())
    doc_id_sets = [set(r["doc_ids"]) for r in ids_list]

    # Pairwise Jaccard
    jaccard_scores = []
    keys = list(group_results.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a, b = doc_id_sets[i], doc_id_sets[j]
            if not a and not b:
                jaccard_scores.append(1.0)
            elif not a or not b:
                jaccard_scores.append(0.0)
            else:
                jaccard_scores.append(len(a & b) / len(a | b))

    avg_jaccard = sum(jaccard_scores) / len(jaccard_scores) if jaccard_scores else 0.0

    return {
        "score": avg_jaccard,
        "pairwise_jaccard": jaccard_scores,
        "questions": keys,
    }


# ---------------------------------------------------------------------------
# Main evaluation runner
# ---------------------------------------------------------------------------

def run_eval(
    eval_path: Path,
    k: int = 5,
    metadata_filter: dict | None = None,
    k_values: list[int] | None = None,
) -> dict:
    """Run the full evaluation suite. Returns comprehensive metrics dict."""
    if not eval_path.exists():
        logger.error("Eval file not found: %s", eval_path)
        return {}

    with open(eval_path, encoding="utf-8") as f:
        questions = json.load(f)

    if not questions:
        logger.warning("Eval file is empty")
        return {"n_questions": 0}

    # Validate question ID uniqueness for correct multi-k caching
    qids = [q.get("id", "?") for q in questions]
    qid_counts = Counter(qids)
    duplicates = {qid: count for qid, count in qid_counts.items() if count > 1}
    if duplicates:
        logger.error(
            "Duplicate question IDs found (this corrupts multi-k metrics): %s",
            duplicates
        )
        return {"n_questions": 0, "error": "duplicate_question_ids"}

    if k_values is None:
        k_values = [k]

    retriever = _load_retriever(k=max(max(k_values), k), metadata_filter=metadata_filter)

    # Warmup: run one retrieval to amortise cold-start costs (model loading,
    # Chroma cache priming) so that latency stats reflect steady-state performance.
    try:
        retriever.invoke("warmup query")
    except Exception:
        pass

    # Per-question results at the primary k
    per_question: list[dict] = []
    latencies: list[float] = []

    # Accumulators for category/source/difficulty breakdowns
    category_metrics: dict[str, list[dict]] = defaultdict(list)
    difficulty_metrics: dict[str, list[dict]] = defaultdict(list)
    source_metrics: dict[str, list[dict]] = defaultdict(list)

    # Consistency groups
    consistency_groups: dict[str, dict[str, dict]] = defaultdict(dict)

    # Cache retrieved docs by question for multi-k sweep
    docs_cache: dict[str, list] = {}

    for q in questions:
        qid = q.get("id", "?")
        query = q.get("query", "")
        expected_keywords = q.get("expected_keywords")
        expected_sources = q.get("expected_sources")
        category = q.get("category", "uncategorized")
        difficulty = q.get("difficulty", "unknown")
        consistency_group = q.get("consistency_group")

        t0 = time.perf_counter()
        docs = retriever.invoke(query)
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)

        # Cache docs for multi-k sweep
        docs_cache[qid] = docs

        # Trim to primary k for scoring
        docs_at_k = docs[:k]
        eval_result = _evaluate_question(docs_at_k, expected_keywords, expected_sources, k)

        result_entry = {
            "id": qid,
            "query": query,
            "category": category,
            "difficulty": difficulty,
            "latency_ms": round(latency_ms, 1),
            **eval_result,
        }
        per_question.append(result_entry)

        # Accumulate by category/difficulty
        category_metrics[category].append(eval_result)
        difficulty_metrics[difficulty].append(eval_result)

        # Accumulate by expected source
        for src in (expected_sources or []):
            source_metrics[src].append(eval_result)

        # Consistency tracking
        if consistency_group:
            doc_ids = [d.metadata.get("doc_id", "") for d in docs_at_k]
            consistency_groups[consistency_group][qid] = {"doc_ids": doc_ids}

    # ---- Aggregate metrics at primary k ----
    n = len(questions)
    hits = sum(1 for r in per_question if r["hit"])
    hit_rate = hits / n if n else 0.0
    mrr = sum(r["reciprocal_rank"] for r in per_question) / n if n else 0.0
    avg_precision = sum(r["precision_at_k"] for r in per_question) / n if n else 0.0
    avg_recall = sum(r["recall_at_k"] for r in per_question) / n if n else 0.0
    avg_ndcg = sum(r["ndcg_at_k"] for r in per_question) / n if n else 0.0

    # ---- Multi-k sweep ----
    multi_k_metrics = {}
    for kv in sorted(k_values):
        kv_hits = 0
        kv_rrs = []
        kv_precisions = []
        kv_recalls = []
        kv_ndcgs = []
        for i, q in enumerate(questions):
            qid = q.get("id", "?")
            expected_keywords = q.get("expected_keywords")
            expected_sources = q.get("expected_sources")
            # Re-use already retrieved docs (we retrieved max(k_values))
            docs = docs_cache[qid]
            docs_kv = docs[:kv]
            ev = _evaluate_question(docs_kv, expected_keywords, expected_sources, kv)
            if ev["hit"]:
                kv_hits += 1
            kv_rrs.append(ev["reciprocal_rank"])
            kv_precisions.append(ev["precision_at_k"])
            kv_recalls.append(ev["recall_at_k"])
            kv_ndcgs.append(ev["ndcg_at_k"])

        multi_k_metrics[kv] = {
            "k": kv,
            "hit_rate": kv_hits / n if n else 0.0,
            "mrr": sum(kv_rrs) / n if n else 0.0,
            "avg_precision_at_k": sum(kv_precisions) / n if n else 0.0,
            "avg_recall_at_k": sum(kv_recalls) / n if n else 0.0,
            "avg_ndcg_at_k": sum(kv_ndcgs) / n if n else 0.0,
        }

    # ---- Category/difficulty/source breakdowns ----
    def _breakdown(groups: dict[str, list[dict]]) -> dict:
        out = {}
        for key, items in sorted(groups.items()):
            n_g = len(items)
            out[key] = {
                "n": n_g,
                "hit_rate": sum(1 for r in items if r["hit"]) / n_g if n_g else 0.0,
                "mrr": sum(r["reciprocal_rank"] for r in items) / n_g if n_g else 0.0,
                "avg_precision_at_k": sum(r["precision_at_k"] for r in items) / n_g if n_g else 0.0,
                "avg_recall_at_k": sum(r["recall_at_k"] for r in items) / n_g if n_g else 0.0,
                "avg_ndcg_at_k": sum(r["ndcg_at_k"] for r in items) / n_g if n_g else 0.0,
            }
        return out

    by_category = _breakdown(category_metrics)
    by_difficulty = _breakdown(difficulty_metrics)
    by_source = _breakdown(source_metrics)

    # ---- Consistency scores ----
    consistency_results = {}
    for group_name, group_data in consistency_groups.items():
        consistency_results[group_name] = _compute_consistency(group_data)

    avg_consistency = (
        sum(c["score"] for c in consistency_results.values()) / len(consistency_results)
        if consistency_results
        else None
    )

    # ---- Latency stats ----
    sorted_latencies = sorted(latencies)
    latency_stats = {}
    if sorted_latencies:
        latency_stats = {
            "min_ms": round(sorted_latencies[0], 1),
            "max_ms": round(sorted_latencies[-1], 1),
            "median_ms": round(sorted_latencies[len(sorted_latencies) // 2], 1),
            "mean_ms": round(sum(sorted_latencies) / len(sorted_latencies), 1),
            "p95_ms": round(sorted_latencies[int(len(sorted_latencies) * 0.95)], 1),
            "p99_ms": round(sorted_latencies[int(len(sorted_latencies) * 0.99)], 1),
        }

    metrics = {
        "n_questions": n,
        "k": k,
        "hit_rate": hit_rate,
        "hits": hits,
        "mrr": mrr,
        "avg_precision_at_k": avg_precision,
        "avg_recall_at_k": avg_recall,
        "avg_ndcg_at_k": avg_ndcg,
        "latency": latency_stats,
        "by_category": by_category,
        "by_difficulty": by_difficulty,
        "by_expected_source": by_source,
        "consistency": {
            "avg_score": avg_consistency,
            "groups": consistency_results,
        },
        "multi_k": multi_k_metrics if len(k_values) > 1 else None,
        "results": per_question,
    }
    return metrics


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def _format_report(metrics: dict) -> list[str]:
    """Format metrics into human-readable log lines."""
    lines = []
    n = metrics["n_questions"]
    k = metrics["k"]

    lines.append(f"Questions: {n}  |  k: {k}")
    lines.append(
        f"Hit Rate: {metrics['hits']}/{n} ({metrics['hit_rate'] * 100:.1f}%)"
    )
    lines.append(f"MRR: {metrics['mrr']:.4f}")
    lines.append(f"Avg Precision@{k}: {metrics['avg_precision_at_k']:.4f}")
    lines.append(f"Avg Recall@{k}: {metrics['avg_recall_at_k']:.4f}")
    lines.append(f"Avg NDCG@{k}: {metrics['avg_ndcg_at_k']:.4f}")

    # Latency
    lat = metrics.get("latency", {})
    if lat:
        lines.append(
            f"Latency: median={lat['median_ms']:.0f}ms  "
            f"p95={lat['p95_ms']:.0f}ms  p99={lat['p99_ms']:.0f}ms  "
            f"mean={lat['mean_ms']:.0f}ms"
        )

    # Category breakdown
    lines.append("")
    lines.append("--- By Category ---")
    for cat, m in sorted(metrics.get("by_category", {}).items()):
        lines.append(
            f"  {cat:30s}  n={m['n']:2d}  hit={m['hit_rate']:.0%}  "
            f"mrr={m['mrr']:.3f}  p@k={m['avg_precision_at_k']:.3f}  "
            f"r@k={m['avg_recall_at_k']:.3f}  ndcg={m['avg_ndcg_at_k']:.3f}"
        )

    # Difficulty breakdown
    lines.append("")
    lines.append("--- By Difficulty ---")
    for diff, m in sorted(metrics.get("by_difficulty", {}).items()):
        lines.append(
            f"  {diff:10s}  n={m['n']:2d}  hit={m['hit_rate']:.0%}  "
            f"mrr={m['mrr']:.3f}  p@k={m['avg_precision_at_k']:.3f}  "
            f"r@k={m['avg_recall_at_k']:.3f}  ndcg={m['avg_ndcg_at_k']:.3f}"
        )

    # Expected source breakdown
    lines.append("")
    lines.append("--- By Expected Source ---")
    for src, m in sorted(metrics.get("by_expected_source", {}).items()):
        lines.append(
            f"  {src:10s}  n={m['n']:2d}  hit={m['hit_rate']:.0%}  "
            f"mrr={m['mrr']:.3f}  p@k={m['avg_precision_at_k']:.3f}  "
            f"r@k={m['avg_recall_at_k']:.3f}  ndcg={m['avg_ndcg_at_k']:.3f}"
        )

    # Consistency
    consistency = metrics.get("consistency", {})
    if consistency.get("avg_score") is not None:
        lines.append("")
        lines.append(f"--- Consistency (avg Jaccard): {consistency['avg_score']:.3f} ---")
        for gname, gdata in sorted(consistency.get("groups", {}).items()):
            lines.append(f"  {gname}: score={gdata['score']:.3f}  questions={gdata['questions']}")

    # Multi-k sweep
    multi_k = metrics.get("multi_k")
    if multi_k:
        lines.append("")
        lines.append("--- Multi-k Sweep ---")
        for kv, m in sorted(multi_k.items()):
            lines.append(
                f"  k={kv:3d}  hit={m['hit_rate']:.0%}  mrr={m['mrr']:.3f}  "
                f"p@k={m['avg_precision_at_k']:.3f}  r@k={m['avg_recall_at_k']:.3f}  "
                f"ndcg={m['avg_ndcg_at_k']:.3f}"
            )

    # Per-question results
    lines.append("")
    lines.append("--- Per-Question Results ---")
    for r in metrics["results"]:
        status = "PASS" if r["hit"] else "FAIL"
        rank_str = f" rank={r['first_hit_rank']}" if r["first_hit_rank"] else ""
        lines.append(
            f"  [{status}] {r['id']:40s} "
            f"p@k={r['precision_at_k']:.2f}  ndcg={r['ndcg_at_k']:.2f}  "
            f"lat={r['latency_ms']:.0f}ms{rank_str}  "
            f"cat={r['category']}  diff={r['difficulty']}"
        )

    return lines


def _build_markdown_report(
    validation: dict | None, metrics: dict | None, k: int
) -> str:
    """Build a markdown report from validation and evaluation results."""
    from datetime import datetime

    parts = [
        "# Medicare RAG Index — Validation & Evaluation Report",
        "",
        f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
        "",
    ]

    if validation:
        parts.extend([
            "## Index Validation",
            "",
            f"- **Result:** {'PASSED' if validation['passed'] else 'FAILED'}",
            f"- **Checks:** {validation['stats'].get('checks_passed', 0)}/{validation['stats'].get('checks_total', 0)} passed",
            f"- **Total documents:** {validation['stats'].get('total_documents', 'N/A')}",
            "",
        ])
        src_dist = validation["stats"].get("source_distribution", {})
        if src_dist:
            parts.append(f"- **Source distribution:** {src_dist}")
        cl = validation["stats"].get("content_length", {})
        if cl:
            parts.append(
                f"- **Content length:** min={cl['min']}, max={cl['max']}, "
                f"median={cl['median']}, mean={cl['mean']:.0f}, p5={cl['p5']}, p95={cl['p95']}"
            )
        emb = validation["stats"].get("embedding_dimension")
        if emb is not None:
            parts.append(f"- **Embedding dimension:** {emb}")
        failed = [c for c in validation["checks"] if not c["passed"]]
        if failed:
            parts.append("")
            parts.append("### Failed checks")
            for c in failed:
                parts.append(f"- {c['name']}: {c['detail']}")
        parts.append("")

    if metrics:
        n = metrics["n_questions"]
        parts.extend([
            f"## Retrieval Evaluation (k={k})",
            "",
            "### Summary",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Questions | {n} |",
            f"| Hit rate | {metrics['hits']}/{n} ({metrics['hit_rate'] * 100:.1f}%) |",
            f"| MRR | {metrics['mrr']:.4f} |",
            f"| Avg Precision@{k} | {metrics['avg_precision_at_k']:.4f} |",
            f"| Avg Recall@{k} | {metrics['avg_recall_at_k']:.4f} |",
            f"| Avg NDCG@{k} | {metrics['avg_ndcg_at_k']:.4f} |",
            "",
        ])
        lat = metrics.get("latency", {})
        if lat:
            parts.extend([
                "### Latency",
                "",
                f"- median: {lat['median_ms']:.0f} ms, p95: {lat['p95_ms']:.0f} ms, p99: {lat['p99_ms']:.0f} ms",
                "",
            ])
        by_cat = metrics.get("by_category", {})
        if by_cat:
            parts.extend([
                "### By category",
                "",
                "| Category | n | Hit rate | MRR | P@k | R@k | NDCG@k |",
                "|----------|---|----------|-----|-----|-----|--------|",
            ])
            for cat, m in sorted(by_cat.items()):
                parts.append(
                    f"| {cat} | {m['n']} | {m['hit_rate']:.0%} | {m['mrr']:.3f} | "
                    f"{m['avg_precision_at_k']:.3f} | {m['avg_recall_at_k']:.3f} | "
                    f"{m['avg_ndcg_at_k']:.3f} |"
                )
            parts.append("")
        by_diff = metrics.get("by_difficulty", {})
        if by_diff:
            parts.extend([
                "### By difficulty",
                "",
                "| Difficulty | n | Hit rate | MRR | P@k | R@k | NDCG@k |",
                "|------------|---|----------|-----|-----|-----|--------|",
            ])
            for diff, m in sorted(by_diff.items()):
                parts.append(
                    f"| {diff} | {m['n']} | {m['hit_rate']:.0%} | {m['mrr']:.3f} | "
                    f"{m['avg_precision_at_k']:.3f} | {m['avg_recall_at_k']:.3f} | "
                    f"{m['avg_ndcg_at_k']:.3f} |"
                )
            parts.append("")
        by_src = metrics.get("by_expected_source", {})
        if by_src:
            parts.extend([
                "### By expected source",
                "",
                "| Source | n | Hit rate | MRR | P@k | R@k | NDCG@k |",
                "|--------|---|----------|-----|-----|-----|--------|",
            ])
            for src, m in sorted(by_src.items()):
                parts.append(
                    f"| {src} | {m['n']} | {m['hit_rate']:.0%} | {m['mrr']:.3f} | "
                    f"{m['avg_precision_at_k']:.3f} | {m['avg_recall_at_k']:.3f} | "
                    f"{m['avg_ndcg_at_k']:.3f} |"
                )
            parts.append("")
        consistency = metrics.get("consistency", {})
        if consistency.get("avg_score") is not None:
            parts.append(f"### Consistency (avg Jaccard): {consistency['avg_score']:.3f}")
            for gname, gdata in sorted(consistency.get("groups", {}).items()):
                parts.append(f"- **{gname}:** {gdata['score']:.3f}")
            parts.append("")
        parts.extend([
            "### Per-question results",
            "",
            "| Status | Question ID | P@k | NDCG@k | Rank | Category | Difficulty |",
            "|--------|----------|-----|--------|------|----------|------------|",
        ])
        for r in metrics["results"]:
            status = "PASS" if r["hit"] else "FAIL"
            rank = r["first_hit_rank"] if r["first_hit_rank"] else "—"
            parts.append(
                f"| {status} | {r['id']} | {r['precision_at_k']:.2f} | {r['ndcg_at_k']:.2f} | "
                f"{rank} | {r['category']} | {r['difficulty']} |"
            )
        parts.append("")

    return "\n".join(parts)


def _format_validation_report(validation: dict) -> list[str]:
    """Format validation results into human-readable log lines."""
    lines = []
    lines.append(
        f"Checks: {validation['stats'].get('checks_passed', 0)}/"
        f"{validation['stats'].get('checks_total', 0)} passed"
    )
    lines.append(f"Total documents: {validation['stats'].get('total_documents', 'N/A')}")

    # Source distribution
    src_dist = validation["stats"].get("source_distribution", {})
    if src_dist:
        lines.append(f"Source distribution: {src_dist}")

    # Content length stats
    cl = validation["stats"].get("content_length", {})
    if cl:
        lines.append(
            f"Content length: min={cl['min']}, max={cl['max']}, "
            f"median={cl['median']}, mean={cl['mean']:.0f}, "
            f"p5={cl['p5']}, p95={cl['p95']}"
        )

    # Embedding dimension
    emb_dim = validation["stats"].get("embedding_dimension")
    if emb_dim is not None:
        lines.append(f"Embedding dimension: {emb_dim}")

    # Metadata keys
    mk = validation["stats"].get("metadata_keys", {})
    if mk:
        lines.append(f"Metadata keys: {mk}")

    # Failed checks
    failed = [c for c in validation["checks"] if not c["passed"]]
    if failed:
        lines.append("")
        lines.append("FAILED CHECKS:")
        for c in failed:
            lines.append(f"  FAIL: {c['name']} - {c['detail']}")

    # Warnings
    if validation["warnings"]:
        lines.append("")
        lines.append("WARNINGS:")
        for w in validation["warnings"]:
            lines.append(f"  WARN: {w}")

    return lines


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comprehensive Medicare RAG index validation and retrieval evaluation."
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
        help="Number of documents to retrieve per query (default: 5).",
    )
    parser.add_argument(
        "--k-values",
        type=str,
        default=None,
        help="Comma-separated k values for multi-k sweep (e.g. 1,3,5,10).",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=DEFAULT_EVAL_PATH,
        help="Path to eval_questions.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print metrics as JSON to stdout.",
    )
    parser.add_argument(
        "--filter-source",
        type=str,
        help="Restrict retrieval to this source (e.g. iom, mcd, codes).",
    )
    parser.add_argument(
        "--filter-category",
        type=str,
        help="Only evaluate questions in this category.",
    )
    parser.add_argument(
        "--filter-difficulty",
        type=str,
        help="Only evaluate questions at this difficulty level.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write a markdown report to PATH (e.g. data/eval_report.md).",
    )
    args = parser.parse_args()

    if args.json:
        logging.getLogger().setLevel(logging.WARNING)

    do_validate = not args.eval_only
    do_eval = not args.validate_only

    metadata_filter = None
    if args.filter_source:
        metadata_filter = {"source": args.filter_source}

    k_values = None
    if args.k_values:
        k_values = [int(x.strip()) for x in args.k_values.split(",")]

    all_output: dict = {}

    # ---- Validation ----
    if do_validate:
        try:
            store, _ = _load_store()
        except Exception as e:
            logger.exception("Failed to load store: %s", e)
            return 1
        logger.info("=" * 60)
        logger.info("=== INDEX VALIDATION ===")
        logger.info("=" * 60)
        validation = validate_index(store)
        all_output["validation"] = validation

        if not args.json:
            for line in _format_validation_report(validation):
                logger.info(line)

        if not validation["passed"]:
            logger.error("Validation FAILED")
            if not do_eval:
                if args.json:
                    print(json.dumps(all_output, indent=2, default=str))
                return 1
            # When both validate and eval are running, still return failure at the end
        else:
            logger.info("Validation PASSED")

    # ---- Evaluation ----
    if do_eval:
        logger.info("=" * 60)
        logger.info("=== RETRIEVAL EVALUATION (k=%d) ===", args.k)
        logger.info("=" * 60)
        if metadata_filter:
            logger.info("Metadata filter: %s", metadata_filter)

        # Pre-filter questions by category/difficulty if requested
        eval_path = args.eval_file
        temp_eval_path = None
        if args.filter_category or args.filter_difficulty:
            with open(eval_path, encoding="utf-8") as f:
                all_questions = json.load(f)
            filtered = all_questions
            if args.filter_category:
                filtered = [q for q in filtered if q.get("category") == args.filter_category]
            if args.filter_difficulty:
                filtered = [q for q in filtered if q.get("difficulty") == args.filter_difficulty]
            if not filtered:
                logger.error(
                    "No questions match filters: category=%s difficulty=%s",
                    args.filter_category,
                    args.filter_difficulty,
                )
                return 1
            # Write filtered questions to a temp file (cleaned up in finally below)
            import tempfile
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tmp:
                json.dump(filtered, tmp, indent=2)
                temp_eval_path = Path(tmp.name)
                eval_path = temp_eval_path

        try:
            if temp_eval_path is not None:
                logger.info(
                    "Filtered to %d questions (category=%s, difficulty=%s)",
                    len(filtered),
                    args.filter_category,
                    args.filter_difficulty,
                )
            metrics = run_eval(
                eval_path,
                k=args.k,
                metadata_filter=metadata_filter,
                k_values=k_values,
            )
            all_output["evaluation"] = metrics

            if not metrics:
                return 1

            if args.json:
                # Strip per-question relevances from JSON to keep it cleaner
                for r in metrics.get("results", []):
                    r.pop("relevances", None)
            else:
                for line in _format_report(metrics):
                    logger.info(line)
        finally:
            # Clean up temp file if created
            if temp_eval_path and temp_eval_path.exists():
                temp_eval_path.unlink()

    if args.report:
        report_path = args.report.resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        md = _build_markdown_report(
            all_output.get("validation"),
            all_output.get("evaluation"),
            args.k,
        )
        report_path.write_text(md, encoding="utf-8")
        logger.info("Report written to %s", report_path)

    if args.json:
        print(json.dumps(all_output, indent=2, default=str))

    # Return failure if validation failed (even if eval also ran)
    if do_validate and not all_output.get("validation", {}).get("passed", True):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
