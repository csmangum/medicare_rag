"""Tests for download scripts (Phase 1)."""
import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from medicare_rag.download._manifest import file_sha256, write_manifest
from medicare_rag.download.codes import download_codes
from medicare_rag.download.iom import download_iom
from medicare_rag.download.mcd import download_mcd


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


def test_mcd_idempotency_skips_when_manifest_exists(tmp_raw: Path) -> None:
    (tmp_raw / "mcd").mkdir(parents=True)
    (tmp_raw / "mcd" / "manifest.json").write_text('{"source_url": "x", "files": []}')

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

    assert len(stream_calls) == 0, "Should not download when manifest exists without --force"


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

    with patch("medicare_rag.download.codes.httpx") as mock_httpx:
        mock_client = MagicMock()
        mock_client.get.side_effect = track_get
        mock_client.stream.side_effect = track_stream
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_httpx.Client.return_value = mock_client

        download_codes(tmp_raw, force=False)

    # Should have called only the page URL to discover link, not the ZIP URL (because file exists)
    assert len(stream_calls) == 0, "Should not re-download HCPCS ZIP when file exists without --force"
