"""Shared manifest writing for download scripts."""
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Return SHA-256 hex digest of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(
    manifest_path: Path,
    source_url: str,
    files: list[tuple[Path, str | None]],
    *,
    base_dir: Path | None = None,
    sources: list[str] | None = None,
) -> None:
    """Write manifest.json with source_url, download_date, and file list with optional hashes.

    files: list of (absolute_path, hash_or_none). If base_dir is set, stored paths are relative to it.
    sources: optional list of URLs for multi-source manifests (e.g. HCPCS + ICD-10-CM).
    """
    base = base_dir or manifest_path.parent
    entries = []
    for fp, fhash in files:
        try:
            rel = fp.resolve().relative_to(base.resolve())
        except ValueError:
            rel = fp
        entries.append({"path": str(rel), "file_hash": fhash})
    data: dict = {
        "source_url": source_url,
        "download_date": datetime.now(UTC).isoformat(),
        "files": entries,
    }
    if sources is not None:
        data["sources"] = sources
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(data, f, indent=2)
