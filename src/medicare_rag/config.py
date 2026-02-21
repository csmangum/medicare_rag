"""Centralized configuration for the Medicare RAG pipeline.

Reads settings from environment variables (via python-dotenv) with sensible
defaults.  Numeric values use safe parsers that log a warning and fall back
to the default when the env value is invalid or out of range.

Exports:
    Paths      — DATA_DIR, RAW_DIR, PROCESSED_DIR, CHROMA_DIR
    Embedding  — EMBEDDING_MODEL, COLLECTION_NAME
    LLM        — LOCAL_LLM_MODEL, LOCAL_LLM_DEVICE, LOCAL_LLM_MAX_NEW_TOKENS,
                  LOCAL_LLM_REPETITION_PENALTY
    Chunking   — CHUNK_SIZE, CHUNK_OVERLAP, LCD_CHUNK_SIZE, LCD_CHUNK_OVERLAP
    Indexing   — CHROMA_UPSERT_BATCH_SIZE, GET_META_BATCH_SIZE
    Retrieval  — LCD_RETRIEVAL_K, HYBRID_SEMANTIC_WEIGHT, HYBRID_KEYWORD_WEIGHT,
                  RRF_K, CROSS_SOURCE_MIN_PER_SOURCE, MAX_QUERY_VARIANTS
    Summary    — ENABLE_TOPIC_SUMMARIES, MAX_DOC_SUMMARY_SENTENCES,
                  MAX_TOPIC_SUMMARY_SENTENCES, MIN_TOPIC_CLUSTER_CHUNKS,
                  MIN_DOC_TEXT_LENGTH_FOR_SUMMARY
    Download   — DOWNLOAD_TIMEOUT, CSV_FIELD_SIZE_LIMIT, ICD10_CM_ZIP_URL
"""
import logging
import math
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _safe_int(key: str, default: int) -> int:
    """Parse *key* from the environment as an int, returning *default* on failure."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %d", key, raw, default)
        return default


def _safe_float(key: str, default: float) -> float:
    """Parse *key* from the environment as a float, returning *default* on failure or non-finite values."""
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        val = float(raw)
        if math.isnan(val) or math.isinf(val):
            logger.warning("Invalid %s=%r (non-finite), using default %s", key, raw, default)
            return default
        return val
    except ValueError:
        logger.warning("Invalid %s=%r, using default %s", key, raw, default)
        return default


def _safe_positive_int(key: str, default: int) -> int:
    """Parse env as int; require value >= 1, else use default and log."""
    val = _safe_int(key, default)
    if val < 1:
        logger.warning("Invalid %s=%d (must be >= 1), using default %d", key, val, default)
        return default
    return val


def _safe_float_positive(key: str, default: float) -> float:
    """Parse env as float; require value > 0, else use default and log."""
    val = _safe_float(key, default)
    if val <= 0:
        logger.warning("Invalid %s=%s (must be > 0), using default %s", key, val, default)
        return default
    return val


# Repo root: directory containing pyproject.toml (when run from repo or editable install)
_REPO_ROOT = Path(__file__).resolve().parents[2]
if not (_REPO_ROOT / "pyproject.toml").exists():
    _REPO_ROOT = Path.cwd()

DATA_DIR = Path(os.environ.get("DATA_DIR", _REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# Phase 3: local embeddings and vector store
CHROMA_DIR = DATA_DIR / "chroma"
COLLECTION_NAME = "medicare_rag"
EMBEDDING_MODEL = os.environ.get(
    "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
)

# Chroma batch sizes (env-overridable; must be >= 1)
CHROMA_UPSERT_BATCH_SIZE = _safe_positive_int("CHROMA_UPSERT_BATCH_SIZE", 5000)
GET_META_BATCH_SIZE = _safe_positive_int("GET_META_BATCH_SIZE", 500)

# ICD-10-CM ZIP URL (optional; when set, codes download includes ICD-10-CM)
ICD10_CM_ZIP_URL: str | None = os.environ.get("ICD10_CM_ZIP_URL") or None

# Download timeout (seconds; must be > 0)
DOWNLOAD_TIMEOUT = _safe_float_positive("DOWNLOAD_TIMEOUT", 60.0)

# MCD CSV max field size (bytes; must be >= 1). Very large policy/narrative fields may exceed
# Python's default; set high enough for real exports but bounded to limit blast radius.
CSV_FIELD_SIZE_LIMIT = _safe_positive_int("CSV_FIELD_SIZE_LIMIT", 10 * 1024 * 1024)

# Chunking defaults (size >= 1; overlap in [0, size))
CHUNK_SIZE = _safe_positive_int("CHUNK_SIZE", 1000)
_chunk_overlap_raw = _safe_int("CHUNK_OVERLAP", 200)
if _chunk_overlap_raw < 0 or _chunk_overlap_raw >= CHUNK_SIZE:
    logger.warning(
        "Invalid CHUNK_OVERLAP=%d (must be 0 <= overlap < CHUNK_SIZE=%d), using default 200",
        _chunk_overlap_raw,
        CHUNK_SIZE,
    )
    CHUNK_OVERLAP = 200
else:
    CHUNK_OVERLAP = _chunk_overlap_raw

# LCD/MCD-specific chunking: larger chunks preserve more policy-text context
LCD_CHUNK_SIZE = _safe_positive_int("LCD_CHUNK_SIZE", 1500)
_lcd_overlap_raw = _safe_int("LCD_CHUNK_OVERLAP", 300)
if _lcd_overlap_raw < 0 or _lcd_overlap_raw >= LCD_CHUNK_SIZE:
    logger.warning(
        "Invalid LCD_CHUNK_OVERLAP=%d (must be 0 <= overlap < LCD_CHUNK_SIZE=%d),"
        " using default 300",
        _lcd_overlap_raw,
        LCD_CHUNK_SIZE,
    )
    LCD_CHUNK_OVERLAP = 300
else:
    LCD_CHUNK_OVERLAP = _lcd_overlap_raw

# LCD retrieval: higher k for coverage-determination queries
LCD_RETRIEVAL_K = _safe_positive_int("LCD_RETRIEVAL_K", 12)

# Topic clustering and summarization
ENABLE_TOPIC_SUMMARIES = os.environ.get("ENABLE_TOPIC_SUMMARIES", "1").strip().lower() in (
    "1", "true", "yes",
)
MAX_DOC_SUMMARY_SENTENCES = _safe_positive_int("MAX_DOC_SUMMARY_SENTENCES", 8)
MAX_TOPIC_SUMMARY_SENTENCES = _safe_positive_int("MAX_TOPIC_SUMMARY_SENTENCES", 10)
MIN_TOPIC_CLUSTER_CHUNKS = _safe_positive_int("MIN_TOPIC_CLUSTER_CHUNKS", 2)
MIN_DOC_TEXT_LENGTH_FOR_SUMMARY = _safe_positive_int("MIN_DOC_TEXT_LENGTH_FOR_SUMMARY", 200)

# Hybrid retrieval: combine semantic and keyword (BM25) search
HYBRID_SEMANTIC_WEIGHT = _safe_float_positive("HYBRID_SEMANTIC_WEIGHT", 0.6)
HYBRID_KEYWORD_WEIGHT = _safe_float_positive("HYBRID_KEYWORD_WEIGHT", 0.4)
RRF_K = _safe_positive_int("RRF_K", 60)

# Cross-source retrieval: ensure results span multiple source types
CROSS_SOURCE_MIN_PER_SOURCE = _safe_positive_int("CROSS_SOURCE_MIN_PER_SOURCE", 2)
MAX_QUERY_VARIANTS = _safe_positive_int("MAX_QUERY_VARIANTS", 6)

# Phase 4: local LLM (Hugging Face pipeline, runs with sentence-transformers stack)
LOCAL_LLM_MODEL = os.environ.get(
    "LOCAL_LLM_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)
LOCAL_LLM_DEVICE = os.environ.get("LOCAL_LLM_DEVICE", "auto")
LOCAL_LLM_MAX_NEW_TOKENS = _safe_positive_int("LOCAL_LLM_MAX_NEW_TOKENS", 512)
LOCAL_LLM_REPETITION_PENALTY = _safe_float_positive(
    "LOCAL_LLM_REPETITION_PENALTY", 1.05
)
