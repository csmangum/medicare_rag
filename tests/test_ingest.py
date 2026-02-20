"""Tests for extraction and chunking (Phase 2)."""
import csv
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from medicare_rag.ingest import extract
from medicare_rag.ingest.chunk import _is_code_doc, _is_mcd_doc, chunk_documents
from medicare_rag.ingest.extract import (
    _cell_to_text,
    _ensure_csv_field_size_limit,
    _extract_mcd_zip,
    _format_date_yyyymmdd,
    _html_to_text,
    _is_mcd_long_text_key,
    _looks_like_icd10_code,
    _meta_schema,
    _parse_hcpcs_line,
    _parse_icd10_xml_root,
    extract_all,
    extract_hcpcs,
    extract_icd10cm,
    extract_iom,
    extract_mcd,
)

# --- Extraction helpers ---


def test_meta_schema() -> None:
    meta = _meta_schema(source="iom", manual="100-02", chapter="6")
    assert meta["source"] == "iom"
    assert meta["manual"] == "100-02"
    assert meta["chapter"] == "6"
    assert meta["title"] is None
    meta2 = _meta_schema(source="codes", hcpcs_code="A1001")
    assert meta2["hcpcs_code"] == "A1001"


def test_is_mcd_long_text_key() -> None:
    assert _is_mcd_long_text_key("Body") is True
    assert _is_mcd_long_text_key("policy_text") is True
    assert _is_mcd_long_text_key("coverage_criteria") is True
    assert _is_mcd_long_text_key("NarrativeText") is True
    assert _is_mcd_long_text_key("policy_date") is False
    assert _is_mcd_long_text_key("policy_datetime") is False
    assert _is_mcd_long_text_key("Effective_Date") is False
    assert _is_mcd_long_text_key("LCD_ID") is False
    assert _is_mcd_long_text_key("") is False


def test_html_to_text() -> None:
    assert _html_to_text("<p>Hello</p>") == "Hello"
    result = _html_to_text("<div><b>Foo</b> bar</div>")
    assert "Foo" in result and "bar" in result
    assert _html_to_text("") == ""


def test_html_to_text_preserves_tables_as_pipe_delimited() -> None:
    """HTML tables are converted to pipe-delimited rows for LCD coverage criteria."""
    html = (
        "<table><tr><th>Code</th><th>Description</th></tr>"
        "<tr><td>G0008</td><td>COVID admin</td></tr>"
        "<tr><td>G0009</td><td>COVID admin 2-dose</td></tr></table>"
    )
    result = _html_to_text(html)
    assert "|" in result
    assert "Code" in result and "Description" in result
    assert "G0008" in result and "COVID admin" in result
    assert "G0009" in result and "COVID admin 2-dose" in result
    # Rows should be on separate lines with cells pipe-separated
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    assert len(lines) >= 2
    assert any("G0008" in line and "COVID admin" in line for line in lines)


def test_cell_to_text_html_empty_returns_none() -> None:
    """HTML that parses to empty text (e.g. empty table) returns None."""
    assert _cell_to_text("Body", "<table><tr><td></td></tr></table>") is None
    assert _cell_to_text("policy", "<p>   \n  </p>") is None


def test_cell_to_text_large_non_html_long_text_included() -> None:
    """Large non-HTML field (>500 chars) is included when key matches long-text heuristic."""
    long_plain = "A" * 600
    result = _cell_to_text("coverage_criteria", long_plain)
    assert result is not None
    assert "coverage_criteria:" in result
    assert long_plain in result
    # Non-long-text key with >500 chars is dropped
    assert _cell_to_text("LCD_ID", "x" * 600) is None


def test_cell_to_text_large_html_in_non_long_text_key_dropped() -> None:
    """HTML in a non-long-text key that extracts to large text is dropped, same as plain text."""
    # HTML that extracts to >500 chars in a non-long-text column (e.g. LCD_ID) should be dropped
    big_html = "<p>" + ("word " * 150) + "</p>"  # ~750 chars of text after strip
    assert _cell_to_text("LCD_ID", big_html) is None
    # Short HTML in same key is still included
    assert _cell_to_text("LCD_ID", "<p>short</p>") == "short"
    # Long-text key with same HTML is included
    assert _cell_to_text("Body", big_html) is not None
    assert "Body:" in _cell_to_text("Body", big_html)


def test_ensure_csv_field_size_limit_overflow_error_halving() -> None:
    """When csv.field_size_limit raises OverflowError, halving loop retries until success."""
    previous_limit = csv.field_size_limit()
    extract._CSV_FIELD_LIMIT_INITIALIZED = False  # noqa: SLF001
    try:
        real_limit = csv.field_size_limit
        setter_calls: list[int] = []

        def mock_limit(desired: int | None = None) -> int | None:
            if desired is None:
                return real_limit()
            setter_calls.append(desired)
            if len(setter_calls) == 1:
                raise OverflowError("platform limit")
            real_limit(desired)
            return None

        with patch("medicare_rag.ingest.extract.csv.field_size_limit", mock_limit):
            limit = _ensure_csv_field_size_limit()
        assert limit == real_limit()
        assert len(setter_calls) >= 2
        assert setter_calls[0] > setter_calls[1]
    finally:
        csv.field_size_limit(previous_limit)
        extract._CSV_FIELD_LIMIT_INITIALIZED = False  # noqa: SLF001


def test_format_date_yyyymmdd() -> None:
    assert _format_date_yyyymmdd("20020701") == "2002-07-01"
    assert _format_date_yyyymmdd("") is None
    assert _format_date_yyyymmdd("123") is None


def test_parse_hcpcs_line() -> None:
    # 320-char fixed width: code 1-5, RIC 11, long 12-91, short 92-119
    line = (
        "A1001"  # 1-5
        + "00100"  # 6-10 seq
        + "7"  # 11 RIC (7 = first modifier)
        + "Dressing for one wound".ljust(80)  # 12-91
        + "Dressing for one wound".ljust(28)  # 92-119
        + " " * (277 - 120)
        + "20020701"  # 277-284
        + "20020701"  # 285-292
        + " " * (320 - 292)
    )
    rec = _parse_hcpcs_line(line)
    assert rec is not None
    assert rec["code"] == "A1001"
    assert rec["ric"] == "7"
    assert "Dressing" in rec["long_desc"]
    assert rec["effective_date"] == "20020701"


# --- IOM extraction (mocked PDF) ---


@pytest.fixture
def tmp_iom_raw(tmp_path: Path) -> Path:
    raw = tmp_path / "raw" / "iom"
    (raw / "100-02").mkdir(parents=True)
    # Create a minimal file so the path exists; we mock pdfplumber
    (raw / "100-02" / "bp102c06.pdf").write_bytes(b"%PDF-1.4 minimal")
    return tmp_path / "raw"


def test_extract_iom_writes_txt_and_meta(tmp_iom_raw: Path, tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Chapter 6 content here."
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch("medicare_rag.ingest.extract.pdfplumber") as mock_plumber:
        mock_plumber.open.return_value = mock_pdf
        written = extract_iom(processed, tmp_iom_raw, force=True)

    assert len(written) == 1
    txt_path, meta_path = written[0]
    assert txt_path.exists()
    assert meta_path.exists()
    assert "Chapter 6 content" in txt_path.read_text()
    meta = json.loads(meta_path.read_text())
    assert meta["source"] == "iom"
    assert meta["manual"] == "100-02"
    assert meta["chapter"] == "6"


# --- MCD extraction (CSV with HTML) ---


@pytest.fixture
def tmp_mcd_raw(tmp_path: Path) -> Path:
    mcd = tmp_path / "raw" / "mcd"
    mcd.mkdir(parents=True)
    # One inner zip containing a CSV with HTML column
    sub = mcd / "current_lcd"
    sub.mkdir(parents=True)
    csv_path = sub / "LCD.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["LCD_ID", "Title", "Body"],
        )
        w.writeheader()
        w.writerow({
            "LCD_ID": "L12345",
            "Title": "Test LCD",
            "Body": "<p>Coverage criteria for <b>test</b>.</p>",
        })
    return tmp_path / "raw"


def test_extract_mcd_writes_txt_and_meta(tmp_mcd_raw: Path, tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    written = extract_mcd(processed, tmp_mcd_raw, force=True)
    assert len(written) >= 1
    txt_path, meta_path = written[0]
    assert txt_path.exists()
    assert meta_path.exists()
    text = txt_path.read_text()
    assert "Coverage criteria" in text
    assert "<p>" not in text
    meta = json.loads(meta_path.read_text())
    assert meta["source"] == "mcd"
    assert meta.get("lcd_id") or "L12345" in str(meta.get("doc_id", ""))


def test_extract_mcd_handles_large_csv_fields(tmp_path: Path) -> None:
    """MCD LCD.csv contains very large policy text fields; extractor should not skip them."""
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    mcd = raw / "mcd" / "current_lcd"
    mcd.mkdir(parents=True)

    huge = "<p>" + ("Policy text " * 20000) + "</p>"  # ~240KB (>200KB)
    csv_path = mcd / "LCD.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["LCD_ID", "Title", "Body"])
        w.writeheader()
        w.writerow({"LCD_ID": "L99999", "Title": "Huge LCD", "Body": huge})

    previous_limit = csv.field_size_limit()
    try:
        written = extract_mcd(processed, raw, force=True)
        assert any(p.name == "L99999.txt" for p, _ in written)
        out_txt = processed / "mcd" / "lcd" / "L99999.txt"
        assert out_txt.exists()
        out = out_txt.read_text()
        assert "Body:" in out
        assert "Policy text" in out
        assert csv.field_size_limit() >= 10 * 1024 * 1024
    finally:
        csv.field_size_limit(previous_limit)
        extract._CSV_FIELD_LIMIT_INITIALIZED = False  # noqa: SLF001


# --- HCPCS extraction (fixed-width lines) ---


@pytest.fixture
def tmp_hcpcs_raw(tmp_path: Path) -> Path:
    codes = tmp_path / "raw" / "codes" / "hcpcs" / "sample"
    codes.mkdir(parents=True)
    # Two records: first line RIC 3 (procedure), second RIC 4 (continuation)
    line1 = (
        "A1001"
        + "00100"
        + "3"
        + "Dressing for one wound".ljust(80)
        + "Dressing for one wound".ljust(28)
        + " " * (277 - 120)
        + "20020701"
        + "20020701"
        + " " * (320 - 292)
    )
    line2 = (
        "A1001"
        + "00200"
        + "4"
        + " (continued description)".ljust(80)
        + "".ljust(28)
        + " " * (320 - 92)
    )
    (codes / "HCPC_sample.txt").write_text(line1 + "\n" + line2 + "\n", encoding="utf-8")
    return tmp_path / "raw"


def test_extract_hcpcs_writes_txt_and_meta(tmp_hcpcs_raw: Path, tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    written = extract_hcpcs(processed, tmp_hcpcs_raw, force=True)
    assert len(written) >= 1
    txt_path, meta_path = written[0]
    assert txt_path.exists()
    assert meta_path.exists()
    text = txt_path.read_text()
    assert "A1001" in text
    assert "Dressing" in text
    assert "continued description" in text
    # Semantic enrichment should be prepended
    assert "HCPCS A-codes" in text
    assert ("Medical" in text and "Supply" in text) or ("Surgical" in text)
    meta = json.loads(meta_path.read_text())
    assert meta["source"] == "codes"
    assert meta.get("hcpcs_code") == "A1001"


# --- extract_all ---


def test_extract_all_respects_source(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    processed = tmp_path / "processed"
    raw.mkdir()
    processed.mkdir()
    (raw / "codes" / "hcpcs" / "x").mkdir(parents=True)
    line = (
        "A1001" + "00100" + "3"
        + "Dressing for one wound".ljust(80)
        + "Short".ljust(28)
        + " " * (277 - 120) + "20020701" + "20020701" + " " * (320 - 292)
    )
    (raw / "codes" / "hcpcs" / "x" / "HCPC_x.txt").write_text(line)
    written = extract_all(processed, raw, source="codes", force=True)
    assert len(written) >= 1


# --- ICD-10-CM extraction (ZIP + XML) ---


@pytest.fixture
def tmp_icd10cm_raw(tmp_path: Path) -> Path:
    """Minimal ICD-10-CM ZIP with one tabular-style XML for code/description pairs."""
    icd_dir = tmp_path / "raw" / "codes" / "icd10-cm"
    icd_dir.mkdir(parents=True)
    zip_path = icd_dir / "icd10cm_sample.zip"
    # Minimal XML: root with elements that have <code> and <desc> (or description) children
    xml_content = """<?xml version="1.0"?>
<root>
  <row><code>A00.0</code><desc>Cholera due to Vibrio cholerae 01, biovar cholerae</desc></row>
  <row><code>A00.1</code><description>Cholera due to Vibrio cholerae 01, biovar el tor</description></row>
</root>
"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tabular.xml", xml_content.encode("utf-8"))
    return tmp_path / "raw"


def test_extract_icd10cm_writes_txt_and_meta(tmp_icd10cm_raw: Path, tmp_path: Path) -> None:
    processed = tmp_path / "processed"
    written = extract_icd10cm(processed, tmp_icd10cm_raw, force=True)
    assert len(written) >= 2
    by_code = {}
    for txt_path, meta_path in written:
        assert txt_path.exists()
        assert meta_path.exists()
        text = txt_path.read_text()
        assert "Code:" in text and "Description:" in text
        meta = json.loads(meta_path.read_text())
        assert meta["source"] == "codes"
        assert "icd10_code" in meta
        by_code[meta["icd10_code"]] = (text, meta)
    assert "A00.0" in by_code
    assert "A00.1" in by_code
    assert "Cholera" in by_code["A00.0"][0]
    # Semantic enrichment should be prepended
    assert "ICD-10-CM" in by_code["A00.0"][0]
    assert "Infectious" in by_code["A00.0"][0]


# --- Chunking ---


def test_is_code_doc() -> None:
    assert _is_code_doc({"source": "codes"}) is True
    assert _is_code_doc({"source": "iom"}) is False


def test_is_mcd_doc() -> None:
    assert _is_mcd_doc({"source": "mcd"}) is True
    assert _is_mcd_doc({"source": "iom"}) is False
    assert _is_mcd_doc({"source": "codes"}) is False
    assert _is_mcd_doc({}) is False


def test_chunk_documents_attaches_metadata(tmp_path: Path) -> None:
    (tmp_path / "iom" / "100-02").mkdir(parents=True)
    (tmp_path / "iom" / "100-02" / "ch6.txt").write_text(
        "First paragraph.\n\nSecond paragraph.\n\nThird paragraph with more content. " * 50
    )
    (tmp_path / "iom" / "100-02" / "ch6.meta.json").write_text(
        '{"source": "iom", "manual": "100-02", "chapter": "6", "doc_id": "iom_100-02_ch6"}'
    )
    docs = chunk_documents(tmp_path, source="iom", chunk_size=100, chunk_overlap=20)
    assert len(docs) >= 2
    regular_docs = [d for d in docs if d.metadata.get("doc_type") not in (
        "document_summary", "topic_summary",
    )]
    assert len(regular_docs) >= 2
    for d in regular_docs:
        assert d.metadata.get("source") == "iom"
        assert "chunk_index" in d.metadata
        assert "total_chunks" in d.metadata


def test_chunk_documents_code_one_chunk_per_doc(tmp_path: Path) -> None:
    (tmp_path / "codes" / "hcpcs").mkdir(parents=True)
    (tmp_path / "codes" / "hcpcs" / "A1001.txt").write_text("Code: A1001\n\nLong description.\n\nShort.")
    (tmp_path / "codes" / "hcpcs" / "A1001.meta.json").write_text(
        '{"source": "codes", "doc_id": "hcpcs_A1001", "hcpcs_code": "A1001"}'
    )
    docs = chunk_documents(tmp_path, source="codes")
    assert len(docs) == 1
    assert docs[0].page_content.strip().startswith("Code:")
    assert docs[0].metadata["source"] == "codes"
    assert "chunk_index" not in docs[0].metadata


# --- Zip path traversal (MCD) ---


def test_extract_mcd_zip_rejects_path_traversal(tmp_path: Path) -> None:
    """Extraction stays under intended directory; no file written via ../ escape."""
    mcd_dir = tmp_path / "mcd"
    mcd_dir.mkdir()
    zip_path = mcd_dir / "evil.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("../outside.csv", b"col1\nval1")
        zf.writestr("safe/subdir/ok.csv", b"LCD_ID,Title\nL1,Test")
    _extract_mcd_zip(mcd_dir, zip_path, "evil")
    assert not (tmp_path.parent / "outside.csv").exists()
    assert (mcd_dir / "evil" / "safe" / "subdir" / "ok.csv").exists()


# --- Chunk when .meta.json missing ---


def test_chunk_documents_without_meta_json(tmp_path: Path) -> None:
    """When only .txt exists, chunking still runs and doc_id is derived from subdir and stem."""
    (tmp_path / "iom" / "100-02").mkdir(parents=True)
    (tmp_path / "iom" / "100-02" / "only_txt.txt").write_text("Some content here.")
    docs = chunk_documents(tmp_path, source="iom")
    assert len(docs) >= 1
    assert docs[0].metadata.get("doc_id") == "iom_only_txt"


# --- ICD-10-CM helpers ---


def test_looks_like_icd10_code() -> None:
    assert _looks_like_icd10_code("A00") is True
    assert _looks_like_icd10_code("A00.0") is True
    assert _looks_like_icd10_code("E11.9") is True
    assert _looks_like_icd10_code("S72.001A") is True
    assert _looks_like_icd10_code("Z99") is True
    # Alphanumeric 3rd character (e.g. obstetric codes)
    assert _looks_like_icd10_code("O9A") is True
    # X placeholder / letters after the dot
    assert _looks_like_icd10_code("T36.0X1A") is True
    assert _looks_like_icd10_code("W19.XXXA") is True
    assert _looks_like_icd10_code("") is False
    assert _looks_like_icd10_code("1") is False
    assert _looks_like_icd10_code("Cholera") is False
    assert _looks_like_icd10_code("A0") is False
    # Ranges must NOT match
    assert _looks_like_icd10_code("A00-B99") is False


def test_parse_icd10_xml_root_cdc_tabular() -> None:
    """CDC tabular XML with <diag> elements containing <name> and <desc>."""
    import xml.etree.ElementTree as ET

    xml_str = """<?xml version="1.0"?>
<ICD10CM.tabular>
  <chapter>
    <name>1</name>
    <desc>Certain infectious and parasitic diseases (A00-B99)</desc>
    <section id="A00-A09">
      <desc>Intestinal infectious diseases (A00-A09)</desc>
      <diag>
        <name>A00</name>
        <desc>Cholera</desc>
        <diag>
          <name>A00.0</name>
          <desc>Cholera due to Vibrio cholerae 01, biovar cholerae</desc>
        </diag>
        <diag>
          <name>A00.1</name>
          <desc>Cholera due to Vibrio cholerae 01, biovar eltor</desc>
        </diag>
      </diag>
    </section>
  </chapter>
</ICD10CM.tabular>"""
    root = ET.fromstring(xml_str)
    pairs = _parse_icd10_xml_root(root)
    codes = {c for c, _ in pairs}
    assert "A00" in codes
    assert "A00.0" in codes
    assert "A00.1" in codes
    # Chapter name "1" should NOT be included
    assert "1" not in codes
    descs = {c: d for c, d in pairs}
    assert "Cholera" in descs["A00"]
    assert "biovar cholerae" in descs["A00.0"]


def test_parse_icd10_xml_root_generic_format() -> None:
    """Fallback generic XML with <code> and <desc> children."""
    import xml.etree.ElementTree as ET

    xml_str = """<?xml version="1.0"?>
<root>
  <row><code>A00.0</code><desc>Cholera</desc></row>
  <row><code>A00.1</code><description>Cholera eltor</description></row>
</root>"""
    root = ET.fromstring(xml_str)
    pairs = _parse_icd10_xml_root(root)
    codes = {c for c, _ in pairs}
    assert "A00.0" in codes
    assert "A00.1" in codes


# --- ICD-10-CM CDC tabular extraction ---


@pytest.fixture
def tmp_icd10cm_cdc_raw(tmp_path: Path) -> Path:
    """ICD-10-CM ZIP with CDC tabular XML format (diag/name/desc)."""
    icd_dir = tmp_path / "raw" / "codes" / "icd10-cm"
    icd_dir.mkdir(parents=True)
    zip_path = icd_dir / "icd10cm_tabular_2025.zip"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<ICD10CM.tabular>
  <chapter>
    <name>1</name>
    <desc>Certain infectious and parasitic diseases (A00-B99)</desc>
    <section id="A00-A09">
      <desc>Intestinal infectious diseases</desc>
      <diag>
        <name>A00</name>
        <desc>Cholera</desc>
        <diag>
          <name>A00.0</name>
          <desc>Cholera due to Vibrio cholerae 01, biovar cholerae</desc>
        </diag>
        <diag>
          <name>A00.1</name>
          <desc>Cholera due to Vibrio cholerae 01, biovar eltor</desc>
        </diag>
      </diag>
    </section>
  </chapter>
  <chapter>
    <name>4</name>
    <desc>Endocrine, nutritional and metabolic diseases (E00-E89)</desc>
    <section id="E08-E13">
      <desc>Diabetes mellitus</desc>
      <diag>
        <name>E11</name>
        <desc>Type 2 diabetes mellitus</desc>
        <diag>
          <name>E11.9</name>
          <desc>Type 2 diabetes mellitus without complications</desc>
        </diag>
      </diag>
    </section>
  </chapter>
</ICD10CM.tabular>
"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("icd10cm_tabular_2025.xml", xml_content.encode("utf-8"))
    return tmp_path / "raw"


def test_extract_icd10cm_cdc_tabular(tmp_icd10cm_cdc_raw: Path, tmp_path: Path) -> None:
    """CDC tabular XML with <diag>/<name>/<desc> produces enriched docs."""
    processed = tmp_path / "processed"
    written = extract_icd10cm(processed, tmp_icd10cm_cdc_raw, force=True)
    assert len(written) >= 4  # A00, A00.0, A00.1, E11, E11.9
    by_code = {}
    for txt_path, meta_path in written:
        assert txt_path.exists()
        assert meta_path.exists()
        text = txt_path.read_text()
        meta = json.loads(meta_path.read_text())
        by_code[meta["icd10_code"]] = (text, meta)
    assert "A00.0" in by_code
    assert "E11.9" in by_code
    # Enrichment from enrich module
    assert "ICD-10-CM" in by_code["A00.0"][0]
    assert "Infectious" in by_code["A00.0"][0]
    assert "ICD-10-CM" in by_code["E11.9"][0]
    assert "Endocrine" in by_code["E11.9"][0] or "Metabolic" in by_code["E11.9"][0]
    # Meta checks
    assert by_code["E11.9"][1]["source"] == "codes"
    assert by_code["E11.9"][1]["doc_id"] == "icd10cm_E11.9"


# --- ICD-10-CM edge cases ---


def test_extract_icd10cm_empty_xml_writes_nothing(tmp_path: Path) -> None:
    """ZIP with XML that has no code/desc elements produces no output files."""
    icd_dir = tmp_path / "raw" / "codes" / "icd10-cm"
    icd_dir.mkdir(parents=True)
    zip_path = icd_dir / "empty.zip"
    xml_content = '<?xml version="1.0"?><root><empty/></root>'
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data.xml", xml_content.encode("utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir()
    written = extract_icd10cm(processed, tmp_path / "raw", force=True)
    assert len(written) == 0


def test_extract_icd10cm_duplicate_code_last_write_wins(tmp_path: Path) -> None:
    """When the same code appears in multiple elements, one output file exists (last write wins)."""
    icd_dir = tmp_path / "raw" / "codes" / "icd10-cm"
    icd_dir.mkdir(parents=True)
    zip_path = icd_dir / "dup.zip"
    xml_content = """<?xml version="1.0"?>
<root>
  <row><code>Z99.0</code><desc>First description</desc></row>
  <row><code>Z99.0</code><desc>Second description wins</desc></row>
</root>
"""
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("tabular.xml", xml_content.encode("utf-8"))
    processed = tmp_path / "processed"
    processed.mkdir()
    extract_icd10cm(processed, tmp_path / "raw", force=True)
    # Extractor appends to written for each element; only one file on disk (last write wins)
    out_dir = processed / "codes" / "icd10cm"
    files = list(out_dir.rglob("*.txt"))
    assert len(files) == 1
    assert "Second description wins" in files[0].read_text()


# --- CLI smoke test ---


def test_chunk_documents_mcd_uses_lcd_chunk_size(tmp_path: Path) -> None:
    """MCD source docs are chunked with the larger LCD chunk size/overlap."""
    (tmp_path / "mcd" / "lcd").mkdir(parents=True)
    long_text = ("LCD policy text about coverage criteria. " * 100).strip()
    (tmp_path / "mcd" / "lcd" / "L12345.txt").write_text(long_text)
    (tmp_path / "mcd" / "lcd" / "L12345.meta.json").write_text(
        json.dumps({"source": "mcd", "doc_id": "mcd_lcd_L12345", "lcd_id": "L12345"})
    )

    small_chunks = chunk_documents(
        tmp_path, source="mcd", lcd_chunk_size=200, lcd_chunk_overlap=50
    )
    large_chunks = chunk_documents(
        tmp_path, source="mcd", lcd_chunk_size=1500, lcd_chunk_overlap=300
    )
    small_regular = [d for d in small_chunks if d.metadata.get("doc_type") not in (
        "document_summary", "topic_summary",
    )]
    large_regular = [d for d in large_chunks if d.metadata.get("doc_type") not in (
        "document_summary", "topic_summary",
    )]
    assert len(small_regular) > len(large_regular)
    for d in large_regular:
        assert d.metadata.get("source") == "mcd"
        assert "chunk_index" in d.metadata


def test_chunk_documents_iom_not_affected_by_lcd_settings(tmp_path: Path) -> None:
    """IOM docs should use the standard chunk_size, not lcd_chunk_size."""
    (tmp_path / "iom" / "100-02").mkdir(parents=True)
    long_text = ("IOM policy text paragraph. " * 100).strip()
    (tmp_path / "iom" / "100-02" / "ch6.txt").write_text(long_text)
    (tmp_path / "iom" / "100-02" / "ch6.meta.json").write_text(
        json.dumps({"source": "iom", "manual": "100-02", "chapter": "6", "doc_id": "iom_100-02_ch6"})
    )

    docs_small_lcd = chunk_documents(
        tmp_path, source="iom", chunk_size=200, chunk_overlap=50,
        lcd_chunk_size=200, lcd_chunk_overlap=50,
    )
    docs_large_lcd = chunk_documents(
        tmp_path, source="iom", chunk_size=200, chunk_overlap=50,
        lcd_chunk_size=5000, lcd_chunk_overlap=500,
    )
    assert len(docs_small_lcd) == len(docs_large_lcd)


def test_ingest_all_skip_extract_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI with --skip-extract and pre-populated processed dir exits 0 and reports chunk count."""
    (tmp_path / "iom" / "100-02").mkdir(parents=True)
    (tmp_path / "iom" / "100-02" / "ch1.txt").write_text("Short.")
    (tmp_path / "iom" / "100-02" / "ch1.meta.json").write_text(
        json.dumps({"source": "iom", "manual": "100-02", "chapter": "1", "doc_id": "iom_100-02_ch1"})
    )
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "ingest_all.py"
    with patch("medicare_rag.config.PROCESSED_DIR", tmp_path), patch("medicare_rag.config.RAW_DIR", tmp_path):
        spec = importlib.util.spec_from_file_location("ingest_all", script_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["ingest_all"] = module
        spec.loader.exec_module(module)
        with patch("sys.argv", ["ingest_all.py", "--skip-extract", "--skip-index"]):
            exit_code = module.main()
    assert exit_code == 0
    out = capsys.readouterr()
    assert "Documents (chunks):" in out.out or "chunks" in out.out.lower()
