"""Chunking with RecursiveCharacterTextSplitter (Phase 2).

Loads extracted .txt + .meta.json from processed_dir and returns LangChain Documents.
"""

import json
import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from medicare_rag.config import CHUNK_OVERLAP, CHUNK_SIZE, LCD_CHUNK_OVERLAP, LCD_CHUNK_SIZE
from medicare_rag.ingest import SourceKind

logger = logging.getLogger(__name__)


def _load_extracted_docs(
    processed_dir: Path,
    source: SourceKind,
) -> list[tuple[str, dict]]:
    """Scan processed_dir for .txt + .meta.json pairs; return (content, metadata) list."""
    processed_dir = Path(processed_dir)
    out: list[tuple[str, dict]] = []
    subdirs = []
    if source == "all":
        subdirs = ["iom", "mcd", "codes"]
    else:
        subdirs = [source]
    for sub in subdirs:
        base = processed_dir / sub
        if not base.exists():
            continue
        for txt_path in base.rglob("*.txt"):
            meta_path = txt_path.parent / f"{txt_path.stem}.meta.json"
            if not meta_path.exists():
                logger.debug("No meta for %s", txt_path)
                meta = {}
            else:
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception as e:
                    logger.warning("Meta read %s: %s", meta_path, e)
                    meta = {}
            try:
                content = txt_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning("Read %s: %s", txt_path, e)
                continue
            meta["doc_id"] = meta.get("doc_id") or f"{sub}_{txt_path.stem}"
            out.append((content, meta))
    return out


def _is_code_doc(meta: dict) -> bool:
    return meta.get("source") == "codes"


def _is_mcd_doc(meta: dict) -> bool:
    return meta.get("source") == "mcd"


def chunk_documents(
    processed_dir: Path,
    *,
    source: SourceKind = "all",
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
    lcd_chunk_size: int = LCD_CHUNK_SIZE,
    lcd_chunk_overlap: int = LCD_CHUNK_OVERLAP,
) -> list[Document]:
    """Load extracted docs from processed_dir and return chunked LangChain Documents.

    Policy docs (IOM) use the standard RecursiveCharacterTextSplitter.
    MCD/LCD documents use larger chunks (lcd_chunk_size / lcd_chunk_overlap) to
    preserve more policy-text context per chunk, improving LCD retrieval.
    Code docs (HCPCS, ICD-10) are kept as one chunk per document (logical grouping).
    """
    processed_dir = Path(processed_dir)
    pairs = _load_extracted_docs(processed_dir, source)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    lcd_splitter = RecursiveCharacterTextSplitter(
        chunk_size=lcd_chunk_size,
        chunk_overlap=lcd_chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    documents: list[Document] = []
    for content, meta in pairs:
        parent_meta = {k: v for k, v in meta.items() if v is not None}
        if _is_code_doc(meta):
            documents.append(Document(page_content=content.strip(), metadata=parent_meta))
        else:
            active_splitter = lcd_splitter if _is_mcd_doc(meta) else splitter
            chunks = active_splitter.split_text(content)
            for i, chunk in enumerate(chunks):
                chunk_meta = dict(parent_meta)
                chunk_meta["chunk_index"] = i
                chunk_meta["total_chunks"] = len(chunks)
                documents.append(Document(page_content=chunk, metadata=chunk_meta))
    return documents
