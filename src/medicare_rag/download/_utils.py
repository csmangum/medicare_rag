"""Shared utilities for download scripts."""
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from medicare_rag.config import DOWNLOAD_TIMEOUT  # noqa: F401

_ALLOWED_SCHEMES = ("http", "https")


def _validate_download_url(url: str) -> None:
    """Raise ValueError if url does not use an allowed scheme (http/https only).

    Prevents file:// or other schemes from being used when env/config is compromised.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Download URL scheme '{scheme or '(empty)'}' not allowed; "
            f"only {', '.join(_ALLOWED_SCHEMES)} permitted"
        )


def stream_download(client: httpx.Client, url: str, dest: Path) -> None:
    """Stream GET url to dest path. Raises on HTTP errors.

    Only http and https URLs are permitted; file:// and other schemes are rejected.
    """
    _validate_download_url(url)
    with client.stream("GET", url) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                if chunk:
                    f.write(chunk)


def sanitize_filename_from_url(url: str, default_basename: str) -> str:
    """Extract a safe filename from a URL (no path traversal).

    Uses only the last path segment and strips query string. Decodes percent-encoding
    before checking for traversal. Returns default_basename if the result would be
    empty or contain path traversal (e.g. "..").
    """
    path = urlparse(url).path or ""
    name = unquote(path.rstrip("/").split("/")[-1].split("?")[0].strip())
    if (
        not name
        or ".." in name
        or "/" in name
        or "\\" in name
        or any(ord(ch) < 32 for ch in name)
    ):
        return default_basename
    return name
