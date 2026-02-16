# Medicare Terminology Embedding Models: Research & Recommendations

## TL;DR

**There is no publicly available embedding model fine-tuned specifically on Medicare terminology.** However, several high-quality biomedical/clinical embedding models exist that significantly outperform generic models (like `all-MiniLM-L6-v2`) on medical text. For this project's RAG pipeline, switching to one of these models is the single highest-impact improvement you can make before considering a custom fine-tune.

---

## Current State (this project)

The project currently uses `sentence-transformers/all-MiniLM-L6-v2` — a general-purpose sentence embedding model trained on broad web text. It works, but it has no understanding of medical abbreviations, ICD/HCPCS code semantics, CMS-specific regulatory language, or clinical terminology relationships.

---

## Publicly Available Biomedical Embedding Models

### Tier 1: Strong Recommendations (drop-in replacements via sentence-transformers)

| Model | Downloads | License | Dim | Notes |
|-------|-----------|---------|-----|-------|
| **`NeuML/pubmedbert-base-embeddings`** | 136K | Apache-2.0 | 768 | BiomedBERT fine-tuned for sentence embeddings on PubMed + clinical text. Best balance of quality, compatibility, and license. **Recommended default for this project.** |
| **`pritamdeka/S-PubMedBert-MS-MARCO`** | 79K | CC-BY-NC-2.0 | 768 | PubMedBERT fine-tuned on MS-MARCO for retrieval. Strong at passage ranking. Non-commercial license. |
| **`pritamdeka/BioBERT-mnli-snli-scinli-scitail-mednli-stsb`** | 38K | CC-BY-NC-3.0 | 768 | BioBERT trained on NLI datasets including MedNLI. Good for semantic similarity in clinical contexts. Non-commercial license. |
| **`sentence-transformers/embeddinggemma-300m-medical`** | 7K | Apache-2.0 | varies | Newer model from the sentence-transformers team, based on Gemma 3, fine-tuned on medical data (MIRIAD dataset). Larger but potentially stronger. |

### Tier 2: Specialized Models (may require more integration work)

| Model | Downloads | License | Notes |
|-------|-----------|---------|-------|
| **`ncbi/MedCPT-Query-Encoder`** + **`ncbi/MedCPT-Article-Encoder`** | 51K / 55K | Custom (NCBI) | Dual-encoder from NCBI. Trained on PubMed query-article pairs. Excellent for medical retrieval but requires separate query/document encoders — not a simple drop-in for LangChain's `HuggingFaceEmbeddings`. |
| **`cambridgeltl/SapBERT-from-PubMedBERT-fulltext`** | 137K | Apache-2.0 | Specialized for biomedical entity linking (UMLS concepts). Excellent at matching medical terms to their canonical forms. Less suited for passage-level retrieval. |
| **`microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`** | 260K | MIT | The base model behind many of the above. Not trained for embeddings directly — needs fine-tuning or a pooling layer for sentence embeddings. |

### Tier 3: Experimental / Niche

| Model | Notes |
|-------|-------|
| `Zybg/synthetic-clinical-embedding-model` | Trained on synthetic clinical data. Very small download count (8). Unproven. |
| `lastmass/Qwen3-Embedding-Medical-0.6B` | Qwen3-based medical embedding. New, small community. |
| `novacardsai/gte-large-medical` | GTE-large fine-tuned on medical data. Only 70 downloads. |
| `vectorranger/embeddinggemma-300m-medical-300k` | Extended fine-tune of the embeddinggemma medical model. Very new. |

---

## Why No Medicare-Specific Model Exists

Medicare terminology sits at the intersection of two domains:

1. **Clinical/biomedical language** — diagnoses, procedures, medical terminology (ICD-10, CPT, clinical notes). Well-served by existing biomedical models.
2. **Federal regulatory/administrative language** — CMS manuals, LCDs, NCDs, MAC jurisdictions, DRG/APC payment systems, coverage determination language, appeals processes.

Biomedical models handle (1) well. The gap is (2) — no one has publicly released a model trained on CMS regulatory text. This is likely because:

- The audience for such a model is narrow (healthcare IT / RCM companies).
- CMS documents are public domain, so the training data is available — but no one has done the work publicly.
- Companies doing this (e.g., Change Healthcare, Optum, Availity) keep their models proprietary.

---

## Recommendation for This Project

### Immediate (no fine-tuning): Switch to `NeuML/pubmedbert-base-embeddings`

This is the single best drop-in upgrade:
- Apache-2.0 license (commercial-friendly)
- sentence-transformers compatible (works with existing `HuggingFaceEmbeddings` code)
- Pre-trained on PubMed abstracts and clinical text
- 768-dim embeddings (vs. 384 for MiniLM) — richer representations
- 136K downloads, well-maintained

**Change required:** Update `EMBEDDING_MODEL` in `config.py` or `.env`:

```
EMBEDDING_MODEL=NeuML/pubmedbert-base-embeddings
```

> **Note:** Changing the embedding model requires re-indexing all documents (`python scripts/ingest_all.py --force`), since the embedding dimensions and semantic space will be different.

### Medium-term: Evaluate on your actual Medicare queries

Use the `scripts/compare_embeddings.py` script (added in this branch) to benchmark multiple models against your eval questions before committing to one. The models to compare:

1. `sentence-transformers/all-MiniLM-L6-v2` (current baseline)
2. `NeuML/pubmedbert-base-embeddings` (recommended)
3. `pritamdeka/S-PubMedBert-MS-MARCO` (if non-commercial license is acceptable)
4. `sentence-transformers/embeddinggemma-300m-medical` (if you have GPU resources)

### Long-term: Fine-tune on Medicare corpus (if retrieval quality plateaus)

If after switching to a biomedical model you still see poor retrieval on Medicare-regulatory queries (e.g., "What modifier is required for bilateral procedures under Part B?", "Does the MAC jurisdiction JL cover cardiac rehab under LCD L35035?"), then fine-tuning is warranted.

**Fine-tuning approach:**

1. **Base model:** Start from `NeuML/pubmedbert-base-embeddings` or `microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`.
2. **Training data:** Generate query-passage pairs from your Medicare corpus:
   - Use the eval questions + their correct retrieved passages as positive pairs.
   - Use GPT-4 or Claude to generate synthetic questions from your CMS document chunks.
   - Mine hard negatives from your ChromaDB (top-k retrievals that are *not* relevant).
3. **Training framework:** `sentence-transformers` with `MultipleNegativesRankingLoss` or `GISTEmbedLoss`.
4. **Scale:** Even 5K-10K high-quality pairs can meaningfully improve domain retrieval.

**Estimated effort:** 2-3 days to generate training data + train. The `sentence-transformers` training loop is straightforward.

---

## Embedding Dimension Comparison

| Model | Dimensions | Model Size | Speed (relative) |
|-------|-----------|------------|-------------------|
| `all-MiniLM-L6-v2` (current) | 384 | 80MB | Fastest |
| `NeuML/pubmedbert-base-embeddings` | 768 | 440MB | ~2x slower |
| `S-PubMedBert-MS-MARCO` | 768 | 440MB | ~2x slower |
| `embeddinggemma-300m-medical` | 1024+ | ~1.2GB | ~4x slower |

The 768-dim models are a good sweet spot — meaningfully better representations without being too large for a local POC.

---

## References

- [NeuML/pubmedbert-base-embeddings](https://huggingface.co/NeuML/pubmedbert-base-embeddings)
- [MedCPT paper (NCBI)](https://arxiv.org/abs/2307.00589)
- [SapBERT paper](https://arxiv.org/abs/2010.11784)
- [BiomedBERT (Microsoft)](https://huggingface.co/microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext)
- [sentence-transformers training guide](https://www.sbert.net/docs/training/overview.html)
- [MIRIAD medical dataset](https://huggingface.co/datasets/tomaarsen/miriad-4.4M-split)
