"""Tests for download scripts (Phase 1)."""
import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from medicare_rag.download._manifest import file_sha256, write_manifest
from medicare_rag.download._utils import sanitize_filename_from_url
from medicare_rag.download.codes import download_codes
from medicare_rag.download.iom import download_iom
from medicare_rag.download.mcd import _safe_extract_zip, download_mcd


def _minimal_zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("readme.txt", "MCD test")
    return buf.getvalue()


@pytest.fixture
def tmp_raw(tmp_path: Path) -> Path:
    return tmp_path / "raw"


def test_manifest_write_and_file_sha256(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    write_manifest(
        tmp_path / "manifest.json",
        "https://example.com/source",
        [(tmp_path / "a.txt", None)],
        base_dir=tmp_path,
    )
    assert (tmp_path / "manifest.json").exists()
    data = (tmp_path / "manifest.json").read_text()
    assert "example.com" in data
    assert "a.txt" in data
    h = file_sha256(tmp_path / "a.txt")
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_mcd_download(tmp_raw: Path) -> None:
    zip_content = _minimal_zip_bytes()
    mock_stream_response = MagicMock()
    mock_stream_response.raise_for_status = MagicMock()
    mock_stream_response.iter_bytes = MagicMock(return_value=iter([zip_content]))

    mock_stream_cm = MagicMock()
    mock_stream_cm.__enter__ = MagicMock(return_value=mock_stream_response)
    mock_stream_cm.__exit__ = MagicMock(return_value=False)

    with patch("medicare_rag.download.mcd.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_cm
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_mcd(tmp_raw, force=True)

    mcd_dir = tmp_raw / "mcd"
    assert mcd_dir.exists()
    assert (mcd_dir / "readme.txt").exists()
    assert (mcd_dir / "readme.txt").read_text() == "MCD test"
    manifest = mcd_dir / "manifest.json"
    assert manifest.exists()
    assert "source_url" in manifest.read_text()
    assert "all_data.zip" in manifest.read_text()


def test_mcd_idempotency_skips_when_manifest_and_file_exist(tmp_raw: Path) -> None:
    mcd_dir = tmp_raw / "mcd"
    mcd_dir.mkdir(parents=True)
    (mcd_dir / "readme.txt").write_text("existing")
    mcd_dir.joinpath("manifest.json").write_text(
        '{"source_url": "x", "files": [{"path": "readme.txt", "file_hash": null}]}'
    )

    stream_calls: list = []

    def track_stream(method, url, **kwargs):
        stream_calls.append(url)
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([_minimal_zip_bytes()]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch("medicare_rag.download.mcd.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.stream.side_effect = track_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_mcd(tmp_raw, force=False)

    assert len(stream_calls) == 0, "Should not download when manifest and listed file exist"


def test_iom_download_discovers_pdfs_and_writes_manifest(tmp_raw: Path) -> None:
    index_html = """
    <html><body>
    <a href="/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms012673">100-02</a>
    <a href="/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms012674">100-03</a>
    <a href="/regulations-and-guidance/guidance/manuals/internet-only-manuals-ioms-items/cms012675">100-04</a>
    </body></html>
    """
    manual_html = """
    <html><body>
    <h2>Downloads</h2>
    <a href="https://www.cms.gov/files/document/chapter-1.pdf">Chapter 1</a>
    <a href="/downloads/bp102c02.pdf">Chapter 2</a>
    </body></html>
    """
    pdf_content = b"%PDF-1.4 fake"

    def fake_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "ioms-items" in url:
            r.text = manual_html
            r.content = None
            return r
        if "internet-only-manuals" in url and "ioms" in url:
            r.text = index_html
            return r
        r.text = ""
        return r

    def fake_stream(method, url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([pdf_content]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch("medicare_rag.download.iom.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.get.side_effect = fake_get
        mock_client.stream.side_effect = fake_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_iom(tmp_raw, force=True)

    iom_dir = tmp_raw / "iom"
    manual_dir = iom_dir / "100-02"
    assert manual_dir.exists()
    pdfs = list(manual_dir.glob("*.pdf"))
    assert len(pdfs) >= 1
    assert (iom_dir / "manifest.json").exists()
    manifest_text = (iom_dir / "manifest.json").read_text()
    assert "source_url" in manifest_text
    assert "100-02" in manifest_text


def test_codes_download_hcpcs_and_manifest(tmp_raw: Path) -> None:
    hcpcs_html = """
    <html><body>
    <a href="/files/zip/january-2026-alpha-numeric-hcpcs-file.zip">January 2026 Alpha-Numeric HCPCS File (ZIP)</a>
    </body></html>
    """
    zip_content = _minimal_zip_bytes()

    def fake_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "quarterly-update" in url:
            r.text = hcpcs_html
            return r
        r.text = ""
        r.content = b""
        return r

    def fake_stream(method, url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([zip_content]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch("medicare_rag.download.codes.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.get.side_effect = fake_get
        mock_client.stream.side_effect = fake_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_codes(tmp_raw, force=True)

    codes_dir = tmp_raw / "codes"
    hcpcs_dir = codes_dir / "hcpcs"
    assert hcpcs_dir.exists()
    zips = list(hcpcs_dir.glob("*.zip"))
    assert len(zips) >= 1
    assert (codes_dir / "manifest.json").exists()


def test_codes_download_icd10cm_when_url_set(tmp_raw: Path) -> None:
    """When ICD10_CM_ZIP_URL is set, download_codes downloads the ICD-10-CM ZIP too."""
    hcpcs_html = """
    <html><body>
    <a href="/files/zip/january-2026-alpha-numeric-hcpcs-file.zip">January 2026 Alpha-Numeric HCPCS File (ZIP)</a>
    </body></html>
    """
    zip_content = _minimal_zip_bytes()
    icd_url = "https://www.cms.gov/files/zip/2025-code-tables-tabular-and-index.zip"

    def fake_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "quarterly-update" in url:
            r.text = hcpcs_html
            return r
        r.text = ""
        r.content = b""
        return r

    def fake_stream(method, url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([zip_content]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with (
        patch("medicare_rag.download.codes.httpx") as mock_httpx,
        patch("medicare_rag.download.codes.ICD10_CM_ZIP_URL", icd_url),
    ):
        mock_client = MagicMock()
        mock_client.get.side_effect = fake_get
        mock_client.stream.side_effect = fake_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_codes(tmp_raw, force=True)

    codes_dir = tmp_raw / "codes"
    hcpcs_dir = codes_dir / "hcpcs"
    icd_dir = codes_dir / "icd10-cm"
    assert hcpcs_dir.exists()
    assert icd_dir.exists()
    icd_zips = list(icd_dir.glob("*.zip"))
    assert len(icd_zips) >= 1
    manifest = codes_dir / "manifest.json"
    assert manifest.exists()
    manifest_text = manifest.read_text()
    assert icd_url in manifest_text


def test_codes_idempotency_skips_existing_file(tmp_raw: Path) -> None:
    hcpcs_dir = tmp_raw / "codes" / "hcpcs"
    hcpcs_dir.mkdir(parents=True)
    existing = hcpcs_dir / "january-2026-alpha-numeric-hcpcs-file.zip"
    existing.write_bytes(_minimal_zip_bytes())

    hcpcs_html = """
    <html><body>
    <a href="/files/zip/january-2026-alpha-numeric-hcpcs-file.zip">January 2026 Alpha-Numeric HCPCS File (ZIP)</a>
    </body></html>
    """
    stream_calls: list = []

    def track_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "quarterly-update" in url:
            r.text = hcpcs_html
            return r
        r.content = _minimal_zip_bytes()
        return r

    def track_stream(method, url, **kwargs):
        stream_calls.append(url)
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([_minimal_zip_bytes()]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with (
        patch("medicare_rag.download.codes.httpx") as mock_httpx,
        patch("medicare_rag.download.codes.ICD10_CM_ZIP_URL", None),
    ):
        mock_client = MagicMock()
        mock_client.get.side_effect = track_get
        mock_client.stream.side_effect = track_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_codes(tmp_raw, force=False)

    # Should have called only the page URL to discover link, not the ZIP URL (because file exists)
    assert len(stream_calls) == 0, "Should not re-download HCPCS ZIP when file exists without --force"


def test_safe_extract_zip_skips_zip_slip(tmp_path: Path) -> None:
    """ZIP entries with path traversal (e.g. ../evil.txt) must not be extracted under output dir."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("safe.txt", "ok")
        z.writestr("../evil.txt", "bad")
        z.writestr("sub/ok.txt", "fine")
    buf.seek(0)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    with zipfile.ZipFile(buf, "r") as zf:
        names = _safe_extract_zip(zf, out_dir)
    assert "safe.txt" in names
    assert "sub/ok.txt" in names
    assert "../evil.txt" not in names
    assert (out_dir / "safe.txt").exists()
    assert (out_dir / "sub" / "ok.txt").exists()
    assert not (out_dir.parent / "evil.txt").exists()
    assert not (tmp_path / "evil.txt").exists()


def test_sanitize_filename_from_url() -> None:
    assert sanitize_filename_from_url("https://example.com/path/to/file.pdf", "default") == "file.pdf"
    assert sanitize_filename_from_url("https://example.com/doc", "default") == "doc"
    assert sanitize_filename_from_url("https://example.com/file.pdf?q=1", "default") == "file.pdf"
    assert sanitize_filename_from_url("https://example.com/", "default") == "default"
    assert sanitize_filename_from_url("https://example.com/..", "default") == "default"
    # Last segment only: ../etc/passwd -> passwd (safe); path/../other.pdf -> other.pdf
    assert sanitize_filename_from_url("https://example.com/../etc/passwd", "default") == "passwd"
    assert sanitize_filename_from_url("https://example.com/path/../other.pdf", "default") == "other.pdf"


def test_sanitize_filename_from_url_encoded_traversal() -> None:
    """Percent-encoded path traversal (e.g. %2e%2e%2f) is decoded then rejected."""
    # %2e%2e%2f decodes to ../
    assert sanitize_filename_from_url("https://example.com/%2e%2e%2fetc%2fpasswd", "default") == "default"
    # %2e%2e decodes to ..
    assert sanitize_filename_from_url("https://example.com/foo%2e%2e", "default") == "default"


def test_sanitize_filename_from_url_empty_and_query() -> None:
    """Empty URL and query-only path return default."""
    assert sanitize_filename_from_url("", "fallback") == "fallback"
    assert sanitize_filename_from_url("https://example.com?", "fallback") == "fallback"


def test_sanitize_filename_from_url_rejects_control_chars() -> None:
    """Percent-encoded NUL or other control chars in basename are rejected (filesystem safety)."""
    # %00 -> NUL
    assert sanitize_filename_from_url("https://example.com/file%00.txt", "default") == "default"
    # %01 -> SOH
    assert sanitize_filename_from_url("https://example.com/doc%01.pdf", "default") == "default"
    # Newline in path segment
    assert sanitize_filename_from_url("https://example.com/foo%0abar", "default") == "default"


def test_iom_duplicate_filenames_disambiguated(tmp_raw: Path) -> None:
    """Two PDFs with the same URL path segment get disambiguated (e.g. document.pdf, document_1.pdf)."""
    index_html = """
    <html><body>
    <a href="/manuals/cms012673">100-02</a>
    <a href="/manuals/cms012674">100-03</a>
    <a href="/manuals/cms012675">100-04</a>
    </body></html>
    """
    manual_html = """
    <html><body>
    <a href="https://cms.gov/docs/document.pdf">First</a>
    <a href="https://cms.gov/other/document.pdf">Second</a>
    </body></html>
    """
    pdf_a = b"%PDF-1.4 first"
    pdf_b = b"%PDF-1.4 second"

    def fake_get(url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        if "ioms-items" in url or "cms01267" in url:
            r.text = manual_html
            return r
        if "internet-only-manuals" in url and "ioms" in url:
            r.text = index_html
            return r
        r.text = ""
        return r

    def fake_stream(method, url, **kwargs):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        content = pdf_b if "other/" in url else pdf_a
        r.iter_bytes = MagicMock(return_value=iter([content]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch("medicare_rag.download.iom.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.get.side_effect = fake_get
        mock_client.stream.side_effect = fake_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_iom(tmp_raw, force=True)

    manual_dir = tmp_raw / "iom" / "100-02"
    pdfs = sorted(manual_dir.glob("*.pdf"))
    assert len(pdfs) >= 2, "Both PDFs should be present (one possibly disambiguated)"
    contents = {p.read_bytes() for p in pdfs}
    assert pdf_a in contents and pdf_b in contents
    manifest_text = (tmp_raw / "iom" / "manifest.json").read_text()
    assert "document" in manifest_text


def test_mcd_redownloads_when_manifest_exists_but_files_missing(tmp_raw: Path) -> None:
    """When manifest.json exists but the listed file is missing, download_mcd re-downloads."""
    mcd_dir = tmp_raw / "mcd"
    mcd_dir.mkdir(parents=True)
    mcd_dir.joinpath("manifest.json").write_text(
        '{"source_url": "x", "files": [{"path": "readme.txt", "file_hash": null}]}'
    )
    # Do not create readme.txt so manifest is stale

    zip_content = _minimal_zip_bytes()
    stream_calls: list = []

    def track_stream(method, url, **kwargs):
        stream_calls.append(url)
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.iter_bytes = MagicMock(return_value=iter([zip_content]))
        cm = MagicMock()
        cm.__enter__ = MagicMock(return_value=r)
        cm.__exit__ = MagicMock(return_value=False)
        return cm

    with patch("medicare_rag.download.mcd.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.stream.side_effect = track_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_mcd(tmp_raw, force=False)

    assert len(stream_calls) == 1, "Should re-download when manifest exists but file is missing"
    assert (mcd_dir / "readme.txt").exists()
    assert "MCD test" in (mcd_dir / "readme.txt").read_text()


def test_config_raw_dir_under_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """When DATA_DIR is set in env, RAW_DIR is DATA_DIR / 'raw'."""
    import importlib

    monkeypatch.setenv("DATA_DIR", "/custom/data")
    from medicare_rag import config as config_module

    importlib.reload(config_module)
    assert config_module.RAW_DIR == Path("/custom/data") / "raw"
