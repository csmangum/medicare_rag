"""Paths and env config. Load .env via python-dotenv.

Default DATA_DIR is best when running from repo root or with an editable install.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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

# Phase 4: local LLM (Hugging Face pipeline, runs with sentence-transformers stack)
LOCAL_LLM_MODEL = os.environ.get(
    "LOCAL_LLM_MODEL", "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
)
LOCAL_LLM_DEVICE = os.environ.get("LOCAL_LLM_DEVICE", "auto")
LOCAL_LLM_MAX_NEW_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_NEW_TOKENS", "512"))
LOCAL_LLM_REPETITION_PENALTY = float(
    os.environ.get("LOCAL_LLM_REPETITION_PENALTY", "1.05")
)
