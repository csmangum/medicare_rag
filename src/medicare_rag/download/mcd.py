"""MCD bulk data download: Download All Data ZIP."""
import logging
import zipfile
from pathlib import Path
from tempfile import NamedTemporaryFile

import httpx

from medicare_rag.download._manifest import file_sha256, write_manifest

logger = logging.getLogger(__name__)

MCD_ALL_DATA_URL = "https://downloads.cms.gov/medicare-coverage-database/downloads/exports/all_data.zip"
DEFAULT_TIMEOUT = 60.0


def download_mcd(raw_dir: Path, *, force: bool = False) -> None:
    """Download MCD 'Download All Data' ZIP and extract to raw_dir/mcd/."""
    out_dir = raw_dir / "mcd"
    manifest_path = out_dir / "manifest.json"

    if not force and manifest_path.exists():
        logger.info("MCD manifest already exists at %s; skipping (use --force to re-download)", manifest_path)
        return

    logger.info("Downloading %s", MCD_ALL_DATA_URL)
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        response = client.get(MCD_ALL_DATA_URL)
        response.raise_for_status()

        with NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(response.content)
            tmp_path = Path(tmp.name)

    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(out_dir)
            names = zf.namelist()
        logger.info("Extracted %d entries to %s", len(names), out_dir)

        files_with_hashes: list[tuple[Path, str | None]] = []
        for name in names:
            full = out_dir / name
            if full.is_file():
                try:
                    h = file_sha256(full)
                except OSError:
                    h = None
                files_with_hashes.append((full, h))

        write_manifest(
            manifest_path,
            MCD_ALL_DATA_URL,
            files_with_hashes,
            base_dir=out_dir,
        )
        logger.info("Wrote manifest to %s", manifest_path)
    finally:
        tmp_path.unlink(missing_ok=True)
