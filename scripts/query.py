#!/usr/bin/env python3
"""Interactive REPL for Medicare RAG. Run the query chain and print cited answers with source metadata.

Usage:
  python scripts/query.py
  python scripts/query.py --filter-source iom --filter-manual 100-02
"""

import argparse
import sys

from medicare_rag.config import CHROMA_DIR, COLLECTION_NAME, OPENROUTER_API_KEY
from medicare_rag.query.chain import build_rag_chain


SOURCE_META_KEYS = ("source", "manual", "chapter", "doc_id", "jurisdiction", "title")


def _check_index_has_docs() -> bool:
    try:
        from medicare_rag.index import get_embeddings, get_or_create_chroma

        embeddings = get_embeddings()
        store = get_or_create_chroma(embeddings)
        n = store._collection.count()
        return n > 0
    except Exception:
        return False


def _main() -> None:
    parser = argparse.ArgumentParser(description="Medicare RAG query REPL")
    parser.add_argument(
        "--filter-source", type=str, help="Filter by source (e.g. iom, mcd, codes)"
    )
    parser.add_argument(
        "--filter-manual", type=str, help="Filter by manual (e.g. 100-02)"
    )
    parser.add_argument(
        "--filter-jurisdiction", type=str, help="Filter by jurisdiction (e.g. JL)"
    )
    parser.add_argument(
        "-k", type=int, default=8, help="Number of chunks to retrieve (default 8)"
    )
    args = parser.parse_args()

    metadata_filter = None
    if args.filter_source or args.filter_manual or args.filter_jurisdiction:
        metadata_filter = {}
        if args.filter_source:
            metadata_filter["source"] = args.filter_source
        if args.filter_manual:
            metadata_filter["manual"] = args.filter_manual
        if args.filter_jurisdiction:
            metadata_filter["jurisdiction"] = args.filter_jurisdiction

    if not OPENROUTER_API_KEY:
        print(
            "Error: OPENROUTER_API_KEY is not set. Set it in the environment or .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not CHROMA_DIR.exists():
        print(
            f"Error: Chroma index not found at {CHROMA_DIR}. Run ingestion first (scripts/ingest_all.py).",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _check_index_has_docs():
        print(
            f"Error: Collection {COLLECTION_NAME} is empty. Run ingestion first (scripts/ingest_all.py).",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Medicare RAG query (blank line to quit)")
    print("---")

    # Build the RAG chain once before the loop to avoid rebuilding on every question
    chain = build_rag_chain(k=args.k, metadata_filter=metadata_filter)

    while True:
        try:
            question = input("Question (blank to quit): ").strip()
        except EOFError:
            break
        if not question:
            break
        try:
            result = chain({"question": question})
            answer = result["answer"]
            source_docs = result["source_documents"]
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            continue
        print()
        print(answer)
        print()
        print("Sources:")
        for i, doc in enumerate(source_docs, start=1):
            meta = doc.metadata
            parts = [f"  [{i}]"]
            for key in SOURCE_META_KEYS:
                if key in meta and meta[key] is not None:
                    parts.append(f"  {key}={meta[key]}")
            print(" ".join(parts))
        print("---")

    print("Bye.")


if __name__ == "__main__":
    _main()
