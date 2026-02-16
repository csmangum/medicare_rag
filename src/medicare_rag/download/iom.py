"""IOM (Internet-Only Manuals) download: 100-02, 100-03, 100-04 chapter PDFs."""

import logging
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from medicare_rag.download._manifest import file_sha256, write_manifest
from medicare_rag.download._utils import sanitize_filename_from_url

logger = logging.getLogger(__name__)

IOM_INDEX_URL = "https://www.cms.gov/medicare/regulations-guidance/manuals/internet-only-manuals-ioms"
TARGET_MANUALS = ("100-02", "100-03", "100-04")
DEFAULT_TIMEOUT = 30.0


def download_iom(raw_dir: Path, *, force: bool = False) -> None:
    """Download IOM chapter PDFs for manuals 100-02, 100-03, 100-04."""
    out_base = raw_dir / "iom"
    out_base.mkdir(parents=True, exist_ok=True)

    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        logger.info("Fetching IOM index %s", IOM_INDEX_URL)
        resp = client.get(IOM_INDEX_URL)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        manual_links: dict[str, str] = {}
        for a in soup.find_all("a", href=True):
            text = (a.get_text() or "").strip()
            if text in TARGET_MANUALS:
                manual_links[text] = urljoin(IOM_INDEX_URL, a["href"])

        if len(manual_links) < len(TARGET_MANUALS):
            found = set(manual_links)
            missing = set(TARGET_MANUALS) - found
            raise RuntimeError(f"Could not find manual links for: {missing}")

        files_with_hashes: list[tuple[Path, str | None]] = []

        for manual_id, manual_url in manual_links.items():
            logger.info("Fetching manual %s: %s", manual_id, manual_url)
            resp = client.get(manual_url)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            pdf_links: list[str] = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if href.lower().endswith(".pdf"):
                    full_url = urljoin(manual_url, href)
                    pdf_links.append(full_url)

            manual_dir = out_base / manual_id
            manual_dir.mkdir(parents=True, exist_ok=True)

            for pdf_url in pdf_links:
                name = sanitize_filename_from_url(pdf_url, "document.pdf")
                if not name.lower().endswith(".pdf"):
                    name += ".pdf"
                dest = manual_dir / name
                if dest.exists() and not force:
                    logger.debug("Skipping (exists): %s", dest)
                    try:
                        h = file_sha256(dest)
                    except OSError:
                        h = None
                    files_with_hashes.append((dest, h))
                    continue

                logger.info("Downloading %s -> %s", pdf_url, dest)
                with client.stream("GET", pdf_url) as r:
                    r.raise_for_status()
                    with dest.open("wb") as f:
                        for chunk in r.iter_bytes():
                            if chunk:
                                f.write(chunk)
                try:
                    h = file_sha256(dest)
                except OSError:
                    h = None
                files_with_hashes.append((dest, h))

        manifest_path = out_base / "manifest.json"
        write_manifest(
            manifest_path,
            IOM_INDEX_URL,
            files_with_hashes,
            base_dir=out_base,
        )
        logger.info("Wrote manifest to %s", manifest_path)
