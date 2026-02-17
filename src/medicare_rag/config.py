"""Paths and env config. Load .env via python-dotenv.

Default DATA_DIR is best when running from repo root or with an editable install.
"""
import logging
import math
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _safe_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r, using default %d", key, raw, default)
        return default


def _safe_float(key: str, default: float) -> float:
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

# Chroma batch sizes (env-overridable)
CHROMA_UPSERT_BATCH_SIZE = _safe_int("CHROMA_UPSERT_BATCH_SIZE", 5000)
GET_META_BATCH_SIZE = _safe_int("GET_META_BATCH_SIZE", 500)

# Download timeout (seconds)
DOWNLOAD_TIMEOUT = _safe_float("DOWNLOAD_TIMEOUT", 60.0)

# Chunking defaults
CHUNK_SIZE = _safe_int("CHUNK_SIZE", 1000)
CHUNK_OVERLAP = _safe_int("CHUNK_OVERLAP", 200)

# Phase 4: local LLM (Hugging Face pipeline, runs with sentence-transformers stack)
LOCAL_LLM_MODEL = os.environ.get(
    "LOCAL_LLM_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)
LOCAL_LLM_DEVICE = os.environ.get("LOCAL_LLM_DEVICE", "auto")
LOCAL_LLM_MAX_NEW_TOKENS = _safe_int("LOCAL_LLM_MAX_NEW_TOKENS", 512)
LOCAL_LLM_REPETITION_PENALTY = _safe_float("LOCAL_LLM_REPETITION_PENALTY", 1.05)
