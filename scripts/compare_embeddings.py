#!/usr/bin/env python3
"""Compare embedding models on Medicare-specific queries.

Loads each candidate model, embeds the eval queries and a set of representative
Medicare text snippets, and reports cosine-similarity metrics to help choose the
best embedding model *before* re-indexing the full corpus.

This is a lightweight, offline comparison -- it does NOT require a populated
Chroma index.  It measures how well each model captures semantic similarity
between Medicare queries and relevant passages.

Usage:
  python scripts/compare_embeddings.py
  python scripts/compare_embeddings.py --models "all-MiniLM-L6-v2,NeuML/pubmedbert-base-embeddings"
  python scripts/compare_embeddings.py --json
"""
import argparse
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

_SCRIPT_DIR = Path(__file__).resolve().parent

DEFAULT_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "NeuML/pubmedbert-base-embeddings",
    "pritamdeka/S-PubMedBert-MS-MARCO",
]

# Representative Medicare passages (hand-written, no corpus needed).
# Each entry is (passage_text, relevant_query_ids).
MEDICARE_PASSAGES = [
    (
        "Medicare Part B covers medically necessary services including doctor "
        "visits, outpatient care, preventive services, and durable medical "
        "equipment. Beneficiaries pay a monthly premium and are responsible "
        "for deductibles and coinsurance.",
        ["coverage_part_b"],
    ),
    (
        "A National Coverage Determination (NCD) is a United States nationwide "
        "determination of whether Medicare will pay for an item or service. "
        "Local Coverage Determinations (LCDs) are decisions made by Medicare "
        "Administrative Contractors (MACs) within their jurisdictions.",
        ["ncd_lcd"],
    ),
    (
        "Medicare claims are submitted electronically using the ANSI X12 837 "
        "format. Providers must include appropriate diagnosis codes (ICD-10-CM), "
        "procedure codes (CPT/HCPCS), and modifiers. Claims go through edits "
        "including NCCI and MUE checks before adjudication.",
        ["claims_processing", "hcpcs_codes", "modifiers"],
    ),
    (
        "HCPCS Level II codes are alphanumeric codes used to identify products, "
        "supplies, and services not included in the CPT code set, such as "
        "ambulance services, durable medical equipment, prosthetics, orthotics, "
        "and supplies (DMEPOS).",
        ["hcpcs_codes"],
    ),
    (
        "Medical necessity requires that services or items be reasonable and "
        "necessary for the diagnosis or treatment of illness or injury. "
        "Documentation must support that the service meets Medicare coverage "
        "criteria and clinical guidelines.",
        ["medical_necessity"],
    ),
    (
        "Medicare modifiers are two-character codes appended to CPT or HCPCS "
        "codes to provide additional information. Common modifiers include -25 "
        "(significant, separately identifiable E/M service), -59 (distinct "
        "procedural service), and -50 (bilateral procedure).",
        ["modifiers"],
    ),
    (
        "The Medicare appeals process has five levels: redetermination by the "
        "MAC, reconsideration by a Qualified Independent Contractor (QIC), "
        "hearing before an Administrative Law Judge (ALJ), review by the "
        "Medicare Appeals Council, and judicial review in federal court.",
        ["appeals"],
    ),
    (
        "Cardiac rehabilitation is a covered Medicare benefit when ordered by "
        "a physician for patients with qualifying conditions including acute "
        "myocardial infarction, coronary artery bypass surgery, or stable "
        "angina pectoris. Programs must be supervised by a physician.",
        ["rehab_coverage"],
    ),
    (
        "Diagnosis Related Groups (DRGs) are a patient classification system "
        "used by Medicare to determine hospital inpatient prospective payment. "
        "Each DRG has a relative weight reflecting the average resource "
        "consumption for cases in that group.",
        [],
    ),
    (
        "The Ambulatory Payment Classification (APC) system is used for "
        "Medicare outpatient prospective payment. Services are grouped into "
        "APCs based on clinical and cost similarity, and each APC has a "
        "fixed payment rate.",
        [],
    ),
]


def _load_eval_queries(eval_path: Path) -> list[dict]:
    """Load eval questions from JSON."""
    if not eval_path.exists():
        logger.warning("Eval file not found: %s -- using built-in queries", eval_path)
        return [
            {"id": "coverage_part_b", "query": "What does Medicare Part B cover?"},
            {"id": "ncd_lcd", "query": "National Coverage Determination vs Local Coverage Determination"},
            {"id": "claims_processing", "query": "How are Medicare claims processed and submitted?"},
            {"id": "hcpcs_codes", "query": "HCPCS Level II codes for supplies and procedures"},
            {"id": "medical_necessity", "query": "Medical necessity documentation requirements"},
            {"id": "modifiers", "query": "CPT modifiers for Medicare billing"},
            {"id": "appeals", "query": "Medicare appeal process for denied claims"},
            {"id": "rehab_coverage", "query": "Coverage for cardiac rehabilitation"},
        ]

    with open(eval_path, encoding="utf-8") as f:
        return json.load(f)


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def evaluate_model(
    model_name: str,
    queries: list[dict],
    passages: list[tuple[str, list[str]]],
) -> dict:
    """Evaluate a single embedding model. Returns metrics dict."""
    from langchain_huggingface import HuggingFaceEmbeddings

    logger.info("Loading model: %s", model_name)
    t0 = time.time()
    try:
        embeddings = HuggingFaceEmbeddings(model_name=model_name)
    except Exception as e:
        logger.error("Failed to load %s: %s", model_name, e)
        return {"model": model_name, "error": str(e)}

    load_time = time.time() - t0
    logger.info("  Loaded in %.1fs", load_time)

    query_texts = [q["query"] for q in queries]
    passage_texts = [p[0] for p in passages]

    t0 = time.time()
    query_vecs = np.array(embeddings.embed_documents(query_texts))
    passage_vecs = np.array(embeddings.embed_documents(passage_texts))
    embed_time = time.time() - t0
    logger.info("  Embedded %d queries + %d passages in %.1fs",
                len(query_texts), len(passage_texts), embed_time)

    # Build query_id -> query_index mapping
    qid_to_idx = {q["id"]: i for i, q in enumerate(queries)}

    # For each query, compute similarity to all passages and rank them
    hits = 0
    reciprocal_ranks = []
    per_query = []

    for qi, q in enumerate(queries):
        qid = q["id"]
        sims = [_cosine_sim(query_vecs[qi], passage_vecs[pi])
                for pi in range(len(passage_texts))]
        ranked_indices = np.argsort(sims)[::-1]

        # Find relevant passages (those whose relevant_query_ids contain this qid)
        relevant_passage_indices = {
            pi for pi, (_, rel_ids) in enumerate(passages) if qid in rel_ids
        }

        first_hit_rank = None
        if relevant_passage_indices:
            for rank, pi in enumerate(ranked_indices, start=1):
                if pi in relevant_passage_indices:
                    first_hit_rank = rank
                    break

        hit = first_hit_rank is not None
        if hit:
            hits += 1
            reciprocal_ranks.append(1.0 / first_hit_rank)
        else:
            reciprocal_ranks.append(0.0)

        top_sim = sims[ranked_indices[0]] if sims else 0.0
        relevant_sim = (
            max(sims[pi] for pi in relevant_passage_indices)
            if relevant_passage_indices else None
        )

        per_query.append({
            "id": qid,
            "hit": hit,
            "first_hit_rank": first_hit_rank,
            "top_similarity": round(top_sim, 4),
            "relevant_similarity": round(relevant_sim, 4) if relevant_sim is not None else None,
        })

    n = len(queries)
    hit_rate = hits / n if n else 0.0
    mrr = sum(reciprocal_ranks) / n if n else 0.0

    # Average similarity between all query-passage pairs (general quality metric)
    all_sims = [_cosine_sim(query_vecs[qi], passage_vecs[pi])
                for qi in range(len(query_texts))
                for pi in range(len(passage_texts))]
    avg_sim = float(np.mean(all_sims))

    return {
        "model": model_name,
        "embedding_dim": int(query_vecs.shape[1]),
        "load_time_s": round(load_time, 1),
        "embed_time_s": round(embed_time, 2),
        "hit_rate": round(hit_rate, 4),
        "mrr": round(mrr, 4),
        "avg_similarity": round(avg_sim, 4),
        "per_query": per_query,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare embedding models on Medicare terminology queries."
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated list of model names to compare. "
             "Default: all-MiniLM-L6-v2, pubmedbert-base-embeddings, S-PubMedBert-MS-MARCO.",
    )
    parser.add_argument(
        "--eval-file",
        type=Path,
        default=_SCRIPT_DIR / "eval_questions.json",
        help="Path to eval_questions.json.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON.",
    )
    args = parser.parse_args()

    models = (
        [m.strip() for m in args.models.split(",")]
        if args.models
        else DEFAULT_MODELS
    )

    queries = _load_eval_queries(args.eval_file)
    logger.info("Comparing %d models on %d queries and %d passages",
                len(models), len(queries), len(MEDICARE_PASSAGES))

    results = []
    for model_name in models:
        result = evaluate_model(model_name, queries, MEDICARE_PASSAGES)
        results.append(result)

    if args.json:
        summaries = []
        for r in results:
            summaries.append({k: v for k, v in r.items() if k != "per_query"})
        print(json.dumps(summaries, indent=2))
    else:
        print("\n" + "=" * 72)
        print("EMBEDDING MODEL COMPARISON — Medicare Terminology")
        print("=" * 72)
        for r in results:
            if "error" in r:
                print(f"\n  {r['model']}: ERROR — {r['error']}")
                continue
            print(f"\n  Model: {r['model']}")
            print(f"    Embedding dim:  {r['embedding_dim']}")
            print(f"    Load time:      {r['load_time_s']}s")
            print(f"    Embed time:     {r['embed_time_s']}s")
            print(f"    Hit rate:       {r['hit_rate']:.1%}")
            print(f"    MRR:            {r['mrr']:.4f}")
            print(f"    Avg similarity: {r['avg_similarity']:.4f}")
            print("    Per-query:")
            for pq in r["per_query"]:
                status = "PASS" if pq["hit"] else "FAIL"
                rank_str = f" rank={pq['first_hit_rank']}" if pq["first_hit_rank"] else ""
                rel_str = f" rel_sim={pq['relevant_similarity']}" if pq["relevant_similarity"] is not None else ""
                print(f"      [{status}] {pq['id']}{rank_str}{rel_str}")
        print("\n" + "=" * 72)
        print("See docs/EMBEDDING_MODELS_RESEARCH.md for detailed recommendations.")
        print("=" * 72 + "\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
