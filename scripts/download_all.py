#!/usr/bin/env python3
"""CLI entry point for downloading IOM, MCD, and code files."""
import argparse
import logging
import sys

from medicare_rag.config import RAW_DIR
from medicare_rag.download import download_codes, download_iom, download_mcd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SOURCES = ("iom", "mcd", "codes", "all")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download Medicare RAG data (IOM, MCD, codes)."
    )
    parser.add_argument(
        "--source",
        choices=SOURCES,
        default="all",
        help="Source to download: iom, mcd, codes, or all (default: all)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even if file already exists",
    )
    args = parser.parse_args()

    raw_dir = RAW_DIR
    raw_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.source in ("iom", "all"):
            logger.info("Downloading IOM manuals 100-02, 100-03, 100-04")
            download_iom(raw_dir, force=args.force)
        if args.source in ("mcd", "all"):
            logger.info("Downloading MCD bulk data")
            download_mcd(raw_dir, force=args.force)
        if args.source in ("codes", "all"):
            logger.info("Downloading ICD-10-CM and HCPCS code files")
            download_codes(raw_dir, force=args.force)
    except NotImplementedError as e:
        logger.error("%s", e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
