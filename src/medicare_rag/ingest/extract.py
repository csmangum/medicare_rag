"""PDF/CSV/XML text extraction (Phase 2).

Output: one .txt + .meta.json per logical document under processed_dir.
"""

import csv
import json
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Literal
from xml.etree.ElementTree import Element

import pdfplumber
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Minimum chars per page to consider pdfplumber extraction "good"
_PDF_MIN_CHARS_PER_PAGE = 50

SourceKind = Literal["iom", "mcd", "codes", "all"]


def _meta_schema(
    *,
    source: str,
    manual: str | None = None,
    chapter: str | None = None,
    title: str | None = None,
    effective_date: str | None = None,
    source_url: str | None = None,
    jurisdiction: str | None = None,
    **extra: str | None,
) -> dict:
    meta = {
        "source": source,
        "manual": manual,
        "chapter": chapter,
        "title": title,
        "effective_date": effective_date,
        "source_url": source_url,
        "jurisdiction": jurisdiction,
    }
    meta.update({k: v for k, v in extra.items() if v is not None})
    return meta


def _write_doc(processed_dir: Path, subdir: str, doc_id: str, text: str, meta: dict) -> tuple[Path, Path]:
    out_dir = processed_dir / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = out_dir / f"{doc_id}.txt"
    meta_path = out_dir / f"{doc_id}.meta.json"
    txt_path.write_text(text, encoding="utf-8")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return txt_path, meta_path


# --- IOM ---

def _should_skip_iom_pdf(name: str) -> bool:
    name_lower = name.lower()
    if "crosswalk" in name_lower or name_lower == "broker-help-desks.pdf":
        return True
    return False


def _iom_chapter_from_path(manual_id: str, rel_path: Path) -> str | None:
    """Derive chapter number from path like 100-02/bp102c06.pdf or 100-04/clm104c01.pdf."""
    stem = rel_path.stem.lower()
    # bp102c06 -> 6, bp102c03pdf -> 3, clm104c01 -> 1
    if manual_id == "100-02" and stem.startswith("bp102c"):
        m = re.search(r"bp102c(\d+)", stem)
        if m:
            return m.group(1).lstrip("0") or "0"
    if manual_id == "100-04" and stem.startswith("clm104c"):
        m = re.search(r"clm104c(\d+)", stem)
        if m:
            return m.group(1).lstrip("0") or "0"
    # 100-03: ncd103c1_part1 -> 1 (part 1)
    if manual_id == "100-03":
        if "ncd103c1_part" in stem:
            m = re.search(r"part(\d+)", stem)
            if m:
                return m.group(1)
        return "1"
    return None


def _extract_pdf_page_unstructured(pdf_path: Path) -> str:
    """Return full document text via unstructured when pdfplumber yields little or no text."""
    # Intentionally broad except: optional dependency; swallow so missing unstructured does not break pipeline.
    try:
        from unstructured.partition.pdf import partition_pdf
        elements = partition_pdf(str(pdf_path), strategy="hi_res")
        texts = []
        for el in elements:
            if hasattr(el, "text"):
                texts.append(el.text)
            else:
                texts.append(str(el))
        full = "\n".join(texts)
        return full.strip()
    except Exception as e:
        logger.debug("Unstructured fallback failed for %s: %s", pdf_path, e)
        return ""


def _extract_iom_pdf(pdf_path: Path, manual_id: str, chapter: str | None) -> str:
    parts = []
    num_pages = 0
    with pdfplumber.open(pdf_path) as pdf:
        num_pages = len(pdf.pages)
        for page in pdf.pages:
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(text)
    result = "\n\n".join(parts)
    # If pdfplumber got nothing or very little (e.g. scanned/image PDF), try unstructured once
    chars_per_page = len(result) / max(1, num_pages)
    if not result.strip() or chars_per_page < _PDF_MIN_CHARS_PER_PAGE:
        fallback = _extract_pdf_page_unstructured(pdf_path)
        if len(fallback) > len(result):
            result = fallback
    return result


def extract_iom(processed_dir: Path, raw_dir: Path, *, force: bool = False) -> list[tuple[Path, Path]]:
    """Extract IOM chapter PDFs to processed_dir/iom/{manual_id}/."""
    iom_dir = raw_dir / "iom"
    if not iom_dir.exists():
        logger.warning("IOM raw dir not found: %s", iom_dir)
        return []
    written: list[tuple[Path, Path]] = []
    for manual_path in sorted(iom_dir.iterdir()):
        if not manual_path.is_dir():
            continue
        manual_id = manual_path.name
        for pdf_path in sorted(manual_path.glob("*.pdf")):
            if _should_skip_iom_pdf(pdf_path.name):
                continue
            chapter = _iom_chapter_from_path(manual_id, pdf_path)
            doc_id = f"ch{chapter}" if chapter else pdf_path.stem
            out_txt = processed_dir / "iom" / manual_id / f"{doc_id}.txt"
            out_meta = processed_dir / "iom" / manual_id / f"{doc_id}.meta.json"
            if not force and out_txt.exists() and out_meta.exists():
                logger.debug("Skip (exists): %s", out_txt)
                written.append((out_txt, out_meta))
                continue
            try:
                text = _extract_iom_pdf(pdf_path, manual_id, chapter)
            except OSError as e:
                logger.warning("Extract failed for %s: %s", pdf_path, e)
                continue
            except Exception as e:
                logger.warning("Extract failed for %s: %s", pdf_path, e)
                raise
            if not text.strip():
                logger.warning("No text recovered for %s; skipping", pdf_path)
                continue
            meta = _meta_schema(
                source="iom",
                manual=manual_id,
                chapter=chapter,
                title=None,
                effective_date=None,
                source_url=None,
                jurisdiction=None,
                doc_id=f"iom_{manual_id}_{doc_id}",
            )
            txt_path, meta_path = _write_doc(processed_dir, f"iom/{manual_id}", doc_id, text, meta)
            written.append((txt_path, meta_path))
            logger.info("Wrote %s (%d chars)", txt_path, len(text))
    return written


# --- MCD ---

def _html_to_text(html: str) -> str:
    if not html or not html.strip():
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def _cell_to_text(k: str, v: str) -> str | None:
    """Return plain text for a cell: strip HTML if present, else return 'k: v' for short values."""
    if not v:
        return None
    s = str(v)
    if "<" in s and ">" in s:
        return _html_to_text(s)
    if len(s) < 500:
        return f"{k}: {v}"
    return None


def _extract_nested_csv_zips(dir_path: Path) -> list[Path]:
    """Extract any *_csv.zip (or *csv*.zip) in dir_path into dir_path; return list of .csv paths."""
    csv_zips = list(dir_path.glob("*_csv.zip")) or list(dir_path.glob("*csv*.zip"))
    for csv_zip in csv_zips:
        try:
            with zipfile.ZipFile(csv_zip, "r") as zf:
                for info in zf.infolist():
                    target = (dir_path / info.filename).resolve()
                    if not target.is_relative_to(dir_path.resolve()):
                        continue
                    zf.extract(info, dir_path)
        except (zipfile.BadZipFile, OSError) as e:
            logger.warning("Failed to extract nested CSV zip %s: %s", csv_zip, e)
    return list(dir_path.rglob("*.csv"))


def _extract_mcd_zip(mcd_dir: Path, inner_zip_path: Path, subdir_name: str) -> list[Path]:
    """Extract inner zip to mcd_dir/subdir_name/; then any nested *_csv.zip; return list of CSV paths."""
    out_sub = mcd_dir / subdir_name
    out_sub.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(inner_zip_path, "r") as zf:
        for info in zf.infolist():
            target = (out_sub / info.filename).resolve()
            if not target.is_relative_to(out_sub.resolve()):
                continue
            zf.extract(info, out_sub)
    csv_files = list(out_sub.rglob("*.csv"))
    if not csv_files:
        csv_files = _extract_nested_csv_zips(out_sub)
    return csv_files


def extract_mcd(processed_dir: Path, raw_dir: Path, *, force: bool = False) -> list[tuple[Path, Path]]:
    """Extract MCD inner ZIPs (LCD, NCD, Article); parse CSV, strip HTML; one doc per row."""
    mcd_dir = raw_dir / "mcd"
    if not mcd_dir.exists():
        logger.warning("MCD raw dir not found: %s", mcd_dir)
        return []
    written: list[tuple[Path, Path]] = []
    # Map inner zip name -> output subtype and id column
    zip_config = [
        ("current_lcd.zip", "lcd", "LCD_ID", "lcd_id"),
        ("all_lcd.zip", "lcd", "LCD_ID", "lcd_id"),
        ("ncd.zip", "ncd", "NCD_ID", "ncd_id"),
        ("current_article.zip", "article", "Article_ID", "article_id"),
        ("all_article.zip", "article", "Article_ID", "article_id"),
    ]
    for zip_name, out_sub, id_col, id_meta_key in zip_config:
        zpath = mcd_dir / zip_name
        extracted_dir = mcd_dir / zip_name.replace(".zip", "")
        csv_files = list(extracted_dir.rglob("*.csv")) if extracted_dir.exists() else []
        if not csv_files and extracted_dir.exists():
            csv_files = _extract_nested_csv_zips(extracted_dir)
        if not csv_files and zpath.exists():
            try:
                csv_files = _extract_mcd_zip(mcd_dir, zpath, zip_name.replace(".zip", ""))
            except Exception as e:
                logger.warning("Failed to extract %s: %s", zpath, e)
                continue
        if not csv_files:
            continue
        for csv_path in csv_files:
            try:
                with open(csv_path, newline="", encoding="utf-8", errors="replace") as f:
                    reader = csv.DictReader(f)
                    fieldnames = list(reader.fieldnames or [])
                    id_col_actual = id_col if id_col in fieldnames else None
                    if not id_col_actual and fieldnames:
                        id_col_actual = (
                            next((c for c in fieldnames if "id" in c.lower() and "lcd" in c.lower()), None)
                            or next((c for c in fieldnames if "id" in c.lower()), None)
                        )
                    count = 0
                    for i, row in enumerate(reader):
                        doc_id = row.get(id_col_actual or "", str(i)).strip() or f"row{i}"
                        doc_id = re.sub(r"[^\w\-]", "_", doc_id)
                        out_txt = processed_dir / "mcd" / out_sub / f"{doc_id}.txt"
                        out_meta = processed_dir / "mcd" / out_sub / f"{doc_id}.meta.json"
                        if not force and out_txt.exists() and out_meta.exists():
                            written.append((out_txt, out_meta))
                            count += 1
                            continue
                        text_parts = []
                        for k, v in row.items():
                            part = _cell_to_text(k, v)
                            if part:
                                text_parts.append(part)
                        text = "\n\n".join(text_parts).strip()
                        if not text:
                            continue
                        meta = _meta_schema(
                            source="mcd",
                            manual=None,
                            chapter=None,
                            title=row.get("Title") or row.get("LCDTitle") or row.get("ArticleTitle"),
                            effective_date=row.get("Effective_Date") or row.get("EffectiveDate"),
                            source_url=row.get("URL"),
                            jurisdiction=row.get("Jurisdiction") or row.get("Contractor"),
                            doc_id=f"mcd_{out_sub}_{doc_id}",
                            **{id_meta_key: doc_id},
                        )
                        txt_path, meta_path = _write_doc(processed_dir, f"mcd/{out_sub}", doc_id, text, meta)
                        written.append((txt_path, meta_path))
                        count += 1
                if count:
                    # count includes both newly written and skipped (when not force)
                    logger.info("MCD %s: %d docs from %s", out_sub, count, csv_path.name)
            except (OSError, csv.Error, UnicodeDecodeError) as e:
                logger.warning("MCD CSV %s: %s", csv_path, e)
    return written


# --- HCPCS (fixed-width 320) ---

# Positions 1-based from record layout
_HCPCS_CODE = (1, 5)
_HCPCS_RIC = (11, 11)
_HCPCS_LONG_DESC = (12, 91)
_HCPCS_SHORT_DESC = (92, 119)
_HCPCS_EFF_DATE = (277, 284)
_HCPCS_TERM_DATE = (285, 292)


def _parse_hcpcs_line(line: str) -> dict | None:
    if len(line) < 120:
        return None
    def slice_1based(start: int, end: int) -> str:
        return line[start - 1 : end].strip()
    return {
        "code": slice_1based(*_HCPCS_CODE),
        "ric": slice_1based(*_HCPCS_RIC),
        "long_desc": slice_1based(*_HCPCS_LONG_DESC),
        "short_desc": slice_1based(*_HCPCS_SHORT_DESC),
        "effective_date": slice_1based(*_HCPCS_EFF_DATE),
        "term_date": slice_1based(*_HCPCS_TERM_DATE),
    }


def _format_date_yyyymmdd(s: str) -> str | None:
    if not s or len(s) != 8:
        return None
    try:
        y, m, d = s[:4], s[4:6], s[6:8]
        return f"{y}-{m}-{d}"
    except (ValueError, IndexError, TypeError):
        return None


def _write_hcpcs_record(
    processed_dir: Path,
    current: dict,
    force: bool,
    written: list[tuple[Path, Path]],
) -> None:
    """Write a single HCPCS record to disk."""
    doc_id = current["code"].strip()
    if not doc_id:
        return
    safe_id = re.sub(r"[^\w\-]", "_", doc_id)
    out_txt = processed_dir / "codes" / "hcpcs" / f"{safe_id}.txt"
    out_meta = processed_dir / "codes" / "hcpcs" / f"{safe_id}.meta.json"
    if not force and out_txt.exists() and out_meta.exists():
        written.append((out_txt, out_meta))
    else:
        content = f"Code: {current['code']}\n\nLong description: {current['long_desc']}\n\nShort description: {current['short_desc']}"
        meta = _meta_schema(
            source="codes",
            manual=None,
            chapter=None,
            title=current["short_desc"] or None,
            effective_date=_format_date_yyyymmdd(current["effective_date"]),
            source_url=None,
            jurisdiction=None,
            doc_id=f"hcpcs_{current['code']}",
            hcpcs_code=current["code"],
            code_type="modifier" if current["ric"] == "7" else "procedure",
        )
        txt_path, meta_path = _write_doc(processed_dir, "codes/hcpcs", safe_id, content, meta)
        written.append((txt_path, meta_path))


def extract_hcpcs(processed_dir: Path, raw_dir: Path, *, force: bool = False) -> list[tuple[Path, Path]]:
    """Parse HCPCS fixed-width .txt; one doc per code (merge continuation lines)."""
    hcpcs_base = raw_dir / "codes" / "hcpcs"
    if not hcpcs_base.exists():
        logger.warning("HCPCS raw dir not found: %s", hcpcs_base)
        return []
    written: list[tuple[Path, Path]] = []
    for hcpcs_file in hcpcs_base.rglob("HCPC*.txt"):
        if "recordlayout" in hcpcs_file.name.lower() or "proc_notes" in hcpcs_file.name.lower():
            continue
        current: dict | None = None
        try:
            lines = hcpcs_file.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            logger.warning("HCPCS read %s: %s", hcpcs_file, e)
            continue
        for line in lines:
            if len(line) < 11:
                continue
            rec = _parse_hcpcs_line(line)
            if not rec:
                continue
            ric = rec["ric"]
            if ric in ("3", "7"):
                if current:
                    _write_hcpcs_record(processed_dir, current, force, written)
                current = rec
            elif ric in ("4", "8") and current:
                current["long_desc"] = (current["long_desc"] + " " + rec["long_desc"]).strip()
            else:
                current = None
        if current and current.get("code", "").strip():
            _write_hcpcs_record(processed_dir, current, force, written)
        logger.info("HCPCS: wrote from %s", hcpcs_file.name)
    return written


# --- ICD-10-CM (optional XML) ---


def _first_child(elem: Element, *names: str) -> Element | None:
    """First direct child matching any of the given tag names (avoids element truth-value)."""
    for name in names:
        child = elem.find(name)
        if child is not None:
            return child
    return None


def extract_icd10cm(processed_dir: Path, raw_dir: Path, *, force: bool = False) -> list[tuple[Path, Path]]:
    """If ICD-10-CM ZIP exists, extract and parse XML for code-description pairs.

    Uses root.iter() over all elements; any element with direct <code> and <desc> (or
    codeValue/description/shortDescription) children produces one doc. When multiple
    elements yield the same code, the same output path is used so the last write wins.
    """
    icd_dir = raw_dir / "codes" / "icd10-cm"
    if not icd_dir.exists():
        return []
    written: list[tuple[Path, Path]] = []
    for zip_path in icd_dir.glob("*.zip"):
        try:
            root = None
            with zipfile.ZipFile(zip_path, "r") as zf:
                xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml") and "tabular" in n.lower()]
                if not xml_names:
                    xml_names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
                if not xml_names:
                    logger.warning("ICD-10-CM %s: no XML files found in archive", zip_path)
                    continue
                for xml_name in xml_names[:1]:
                    with zf.open(xml_name) as f:
                        root = ET.parse(f).getroot()
                    break
            if root is None:
                logger.warning("ICD-10-CM %s: failed to parse XML root element", zip_path)
                continue
            # Common CDC structure: diag/diagCode or similar
            for elem in root.iter():
                code = _first_child(elem, "code", "codeValue", "code_value")
                desc = _first_child(elem, "desc", "description", "shortDescription")
                if code is not None and desc is not None and (code.text or "").strip():
                    code_val = (code.text or "").strip()
                    desc_val = (desc.text or "").strip()
                    if not code_val:
                        continue
                    doc_id = re.sub(r"[^\w\-.]", "_", code_val)
                    out_txt = processed_dir / "codes" / "icd10cm" / f"{doc_id}.txt"
                    out_meta = processed_dir / "codes" / "icd10cm" / f"{doc_id}.meta.json"
                    if not force and out_txt.exists() and out_meta.exists():
                        written.append((out_txt, out_meta))
                        continue
                    content = f"Code: {code_val}\n\nDescription: {desc_val}"
                    meta = _meta_schema(
                        source="codes",
                        manual=None,
                        chapter=None,
                        title=desc_val[:200] if desc_val else None,
                        effective_date=None,
                        source_url=None,
                        jurisdiction=None,
                        doc_id=f"icd10cm_{code_val}",
                        icd10_code=code_val,
                    )
                    txt_path, meta_path = _write_doc(processed_dir, "codes/icd10cm", doc_id, content, meta)
                    written.append((txt_path, meta_path))
        except (zipfile.BadZipFile, ET.ParseError, OSError) as e:
            logger.warning("ICD-10-CM %s: %s", zip_path, e)
    return written


# --- Public API ---

def extract_all(
    processed_dir: Path,
    raw_dir: Path,
    *,
    source: SourceKind = "all",
    force: bool = False,
) -> list[tuple[Path, Path]]:
    """Run extractors and write one .txt + .meta.json per document. Returns list of (txt_path, meta_path)."""
    processed_dir = Path(processed_dir)
    raw_dir = Path(raw_dir)
    all_written: list[tuple[Path, Path]] = []
    if source in ("iom", "all"):
        all_written.extend(extract_iom(processed_dir, raw_dir, force=force))
    if source in ("mcd", "all"):
        all_written.extend(extract_mcd(processed_dir, raw_dir, force=force))
    if source in ("codes", "all"):
        all_written.extend(extract_hcpcs(processed_dir, raw_dir, force=force))
        all_written.extend(extract_icd10cm(processed_dir, raw_dir, force=force))
    return all_written
