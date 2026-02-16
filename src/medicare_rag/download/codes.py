"""Code files download: ICD-10-CM and HCPCS."""
import logging
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from medicare_rag.download._manifest import file_sha256, write_manifest

logger = logging.getLogger(__name__)

HCPCS_QUARTERLY_URL = "https://www.cms.gov/medicare/coding-billing/healthcare-common-procedure-system/quarterly-update"
# ICD-10-CM: set ICD10_CM_ZIP_URL in env to a CDC ZIP (e.g. from https://www.cdc.gov/nchs/icd/icd-10-cm.htm or FTP)
ICD10_CM_ZIP_URL_ENV = "ICD10_CM_ZIP_URL"
DEFAULT_TIMEOUT = 60.0


def _latest_hcpcs_zip_url(client: httpx.Client) -> str | None:
    """Parse CMS quarterly page and return URL of latest Alpha-Numeric HCPCS File (ZIP)."""
    resp = client.get(HCPCS_QUARTERLY_URL)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    # Look for links like "January 2026 Alpha-Numeric HCPCS File (ZIP)"
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").strip()
        if "alpha-numeric" in text.lower() and "hcpcs" in text.lower() and "zip" in text.lower():
            return urljoin(HCPCS_QUARTERLY_URL, a["href"])
    return None


def download_codes(raw_dir: Path, *, force: bool = False) -> None:
    """Download ICD-10-CM (if URL set) and HCPCS code files."""
    out_base = raw_dir / "codes"
    out_base.mkdir(parents=True, exist_ok=True)
    files_with_hashes: list[tuple[Path, str | None]] = []

    with httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True) as client:
        # HCPCS
        hcpcs_dir = out_base / "hcpcs"
        hcpcs_dir.mkdir(parents=True, exist_ok=True)
        zip_url = _latest_hcpcs_zip_url(client)
        if not zip_url:
            logger.warning("Could not find latest HCPCS ZIP link on %s", HCPCS_QUARTERLY_URL)
        else:
            # Use last segment of URL as filename, or a safe default
            name = zip_url.rstrip("/").split("/")[-1].split("?")[0] or "hcpcs.zip"
            if not name.lower().endswith(".zip"):
                name += ".zip"
            dest = hcpcs_dir / name
            if dest.exists() and not force:
                logger.info("HCPCS file already exists: %s (use --force to re-download)", dest)
                try:
                    files_with_hashes.append((dest, file_sha256(dest)))
                except OSError:
                    files_with_hashes.append((dest, None))
            else:
                logger.info("Downloading HCPCS %s -> %s", zip_url, dest)
                r = client.get(zip_url)
                r.raise_for_status()
                dest.write_bytes(r.content)
                try:
                    files_with_hashes.append((dest, file_sha256(dest)))
                except OSError:
                    files_with_hashes.append((dest, None))

        # ICD-10-CM (optional, from env)
        icd_url = os.environ.get(ICD10_CM_ZIP_URL_ENV)
        if icd_url:
            icd_dir = out_base / "icd10-cm"
            icd_dir.mkdir(parents=True, exist_ok=True)
            name = icd_url.rstrip("/").split("/")[-1].split("?")[0] or "icd10cm.zip"
            if not name.lower().endswith(".zip"):
                name += ".zip"
            dest = icd_dir / name
            if dest.exists() and not force:
                logger.info("ICD-10-CM file already exists: %s (use --force to re-download)", dest)
                try:
                    files_with_hashes.append((dest, file_sha256(dest)))
                except OSError:
                    files_with_hashes.append((dest, None))
            else:
                logger.info("Downloading ICD-10-CM %s -> %s", icd_url, dest)
                r = client.get(icd_url)
                r.raise_for_status()
                dest.write_bytes(r.content)
                try:
                    files_with_hashes.append((dest, file_sha256(dest)))
                except OSError:
                    files_with_hashes.append((dest, None))
        else:
            logger.info(
                "ICD-10-CM skipped: set %s to a CDC ZIP URL to download (e.g. from cdc.gov/nchs/icd/icd-10-cm)",
                ICD10_CM_ZIP_URL_ENV,
            )

    manifest_path = out_base / "manifest.json"
    write_manifest(
        manifest_path,
        HCPCS_QUARTERLY_URL,
        files_with_hashes,
        base_dir=out_base,
    )
    logger.info("Wrote manifest to %s", manifest_path)
