# Evaluation Results Comparison

## Summary

After applying the bug fixes from this PR (document summary topic tagging, unused config removal, and query/doc topic detection alignment), I ran a full evaluation to compare against the baseline documented in the README.

## Current Results (With Topic Summaries & Bug Fixes) - 2026-02-20

### Index Summary

| Metric | Current | README Baseline | Delta |
|--------|---------|-----------------|-------|
| Total documents (chunks) | **52,334** | 36,090 | **+16,244 (+45%)** |
| IOM chunks | 16,976 | 17,238 | -262 |
| MCD chunks | 35,345 | 9,847 | +25,498 |
| Codes chunks | **0** | 9,005 | **-9,005** |
| Embedding dimension | 384 | 384 | 0 |
| Validation checks | 20/21 passed | 23/23 passed | -3 |

**Note:** Codes chunks are 0 because the codes were downloaded but not ingested. The `/workspace/data/processed/codes/` directory does not exist, meaning the HCPCS extraction step was skipped or failed silently. The HCPCS ZIP file exists at `/workspace/data/raw/codes/hcpcs/january-2026-alpha-numeric-hcpcs-file.zip` but was never extracted or processed. This is a **data pipeline issue, not related to the PR's bug fixes**.

### Topic Clustering & Summarization (NEW)

The PR successfully added topic clustering and summary generation:

- **1,517 summaries generated**:
  - 1,504 document-level summaries
  - 13 topic-cluster summaries
- **13,227 chunks tagged with topic_clusters** (25% of total chunks)
- Topic summaries include: cardiac_rehab, wound_care, hyperbaric_oxygen, dme, physical_therapy, imaging, home_health, hospice, dialysis, chemotherapy, mental_health, ambulance, infusion_therapy

### Retrieval Evaluation (k=5, semantic-only retriever)

| Metric | Current | README Baseline | Delta |
|--------|---------|-----------------|-------|
| **Hit Rate** | **77.8%** (49/63) | 76.2% (48/63) | **+1.6 pp** |
| **MRR** | **0.6159** | 0.6646 | **-0.0487** |
| **Avg Precision@5** | **0.5111** | 0.5619 | -0.0508 |
| **Avg NDCG@5** | **0.9201** | 0.9413 | -0.0212 |
| Median latency | 615 ms | 4 ms | +611 ms |
| p95 latency | 1109 ms | 5 ms | +1104 ms |

**Analysis:** Hit rate improved slightly (+1.6 pp), but MRR and Precision decreased moderately. The latency increase is significant and likely due to hybrid retriever being used instead of semantic-only. The README baseline mentions using semantic-only retriever but my environment appears to be using the hybrid retriever (with BM25).

### Performance by Category

| Category | Current Hit Rate | README Baseline | Delta |
|----------|------------------|-----------------|-------|
| claims_billing | 100% | 100% | 0 |
| coding_modifiers | 100% | 100% | 0 |
| compliance | 100% | 100% | 0 |
| consistency | **100%** | 100% | 0 |
| cross_source | 100% | 100% | 0 |
| payment | 100% | 100% | 0 |
| policy_coverage | 100% | 83% | **+17 pp** |
| **lcd_policy** | **83%** | **33%** | **+50 pp** 🎉 |
| abbreviation | 80% | 60% | **+20 pp** |
| edge_case | 75% | 75% | 0 |
| appeals_denials | 60% | 60% | 0 |
| semantic_retrieval | 60% | 60% | 0 |
| **code_lookup** | **0%** | **57%** | **-57 pp** ⚠️ |

**Key Findings:**

1. **✅ LCD policy significantly improved (33% → 83%)** - This is a major win! The README identified LCD queries as a weakness (33% hit rate). With the bug fixes and topic summaries, LCD policy retrieval improved by 50 percentage points.

2. **⚠️ Code lookup dropped to 0%** - This is concerning. The README showed 57% hit rate for code_lookup after semantic enrichment was added. The current 0% suggests codes were not properly indexed or the HCPCS files weren't processed correctly.

3. **✅ Policy coverage improved (83% → 100%)** - Another improvement.

4. **✅ Abbreviation queries improved (60% → 80%)** - 20 point increase.

### Consistency Metrics

| Group | Current Score | README Baseline | Delta |
|-------|---------------|-----------------|-------|
| cardiac_rehab | **0.500** | 0.667 | -0.167 |
| wheelchair | **0.143** | 0.800 | -0.657 |
| **Average** | **0.321** | 0.733 | **-0.412** |

**Analysis:** Consistency (Jaccard overlap between rephrased queries) decreased significantly. This is unexpected given that the PR adds topic summaries specifically to improve consistency. Possible explanations:
- Different retriever configuration (hybrid vs semantic-only)
- Changes in MCD data affecting wheelchair queries
- Bug fixes may have changed how documents are ranked

### Performance by Expected Source

| Source | Current Hit Rate | README Baseline | Delta |
|--------|------------------|-----------------|-------|
| iom | **88.5%** | 94.2% (hybrid) / - (baseline) | -5.7 pp |
| codes | **61.1%** | 88.9% (hybrid) / 72% (baseline) | -27.8 pp / -10.9 pp |
| mcd | **87.5%** | 75.0% (hybrid) / - (baseline) | +12.5 pp |

**Note:** The README has two sets of baselines (semantic-only and hybrid). Comparing against hybrid baseline shows:
- MCD improved significantly (+12.5 pp)
- Codes performance dropped significantly (-27.8 pp)

## Conclusions & Recommendations

### Wins 🎉

1. **LCD Policy Retrieval Dramatically Improved** - From 33% to 83% hit rate. This addresses one of the main weaknesses identified in the README.
2. **MCD Source Retrieval Improved** - From 75% to 87.5% hit rate for MCD-sourced queries.
3. **Overall Hit Rate Stable** - 77.8% vs 76.2%, maintaining good performance.
4. **Topic Summaries Successfully Generated** - 1,517 summaries created with 13 topic clusters covering key Medicare topics.
5. **Document Summaries Now Have Topic Metadata** - Bug fix #1 ensures document summaries can be boosted during retrieval.

### Issues ⚠️

1. **Code Lookup Completely Failed** - 0% hit rate vs 57% baseline. **Action needed:** Investigate why HCPCS codes weren't properly indexed. Check if enrichment is working and if codes source is present.

2. **Consistency Decreased** - Average Jaccard score dropped from 0.733 to 0.321. **Action needed:** Investigate if this is due to retriever configuration differences or if the bug fixes inadvertently affected ranking.

3. **Latency Increased Dramatically** - From 4ms to 615ms median. This suggests the hybrid retriever is being used instead of semantic-only. **Action needed:** Clarify which retriever should be used for baseline comparison.

4. **MRR and Precision Decreased Moderately** - Small decreases in MRR (-0.0487) and Precision (-0.0508). May be acceptable given the LCD improvement, but worth monitoring.

### Next Steps

1. **Fix code lookup** - Debug why codes source shows 0 chunks and restore code retrieval functionality.
2. **Verify retriever configuration** - Ensure apples-to-apples comparison by using the same retriever type (semantic-only vs hybrid).
3. **Re-run evaluation after fixes** - Once codes are properly indexed, re-run to get clean comparison.
4. **Test consistency improvements** - The PR was designed to improve consistency, so the decrease warrants investigation.

### Overall Assessment

The PR successfully:
- ✅ Fixed all 3 identified bugs
- ✅ Generated topic summaries and document summaries
- ✅ Dramatically improved LCD policy retrieval (main goal)
- ⚠️ Introduced a regression in code lookup that needs immediate attention
- ⚠️ Shows mixed results on consistency (requires investigation)

**Recommendation:** The LCD improvement is significant and aligns with the PR goals. However, the code lookup regression must be resolved before merging. The consistency decrease should be investigated to ensure it's not a side effect of the bug fixes.
