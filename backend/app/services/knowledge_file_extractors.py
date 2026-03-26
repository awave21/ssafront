from __future__ import annotations

import csv
import io
import os
import re
from typing import Iterable


_CYRILLIC_OR_LATIN_RE = re.compile(r"[A-Za-zА-Яа-я]")


def _decode_csv_bytes(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return content.decode("cp1251")
    except UnicodeDecodeError:
        pass
    return content.decode("latin-1", errors="replace")


def _detect_csv_delimiter(text: str) -> str:
    sample_lines = text.split("\n")[:10]
    sample = "\n".join(sample_lines)
    candidates = [";", ",", "\t"]
    counts = {d: sample.count(d) for d in candidates}
    # Prefer most common delimiter.
    best = max(candidates, key=lambda d: counts[d])
    return best if counts[best] > 0 else ","


def _row_to_text(header: list[str] | None, row: list[str]) -> str:
    if not header:
        return "; ".join((c or "").strip() for c in row if (c or "").strip())

    parts: list[str] = []
    for i in range(min(len(header), len(row))):
        h = (header[i] or "").strip()
        v = (row[i] or "").strip()
        if not h or not v:
            continue
        parts.append(f"{h}: {v}")
    return "; ".join(parts)


def extract_text_from_csv_bytes(content: bytes) -> str:
    text = _decode_csv_bytes(content)
    delimiter = _detect_csv_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = [row for row in reader if any((c or "").strip() for c in row)]
    if not rows:
        return ""

    header = rows[0]
    has_header = any(_CYRILLIC_OR_LATIN_RE.search((c or "")) for c in header)
    if has_header:
        header_out = [str(c or "").strip() for c in header]
        data_rows = rows[1:]
    else:
        header_out = None
        data_rows = rows

    lines = [_row_to_text(header_out, [str(c or "") for c in r]) for r in data_rows]
    return "\n".join(line for line in lines if line.strip())


def _extract_pdf_text_pypdf(content: bytes, *, extraction_mode: str) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PDF extraction requires the pypdf package (install backend requirements)."
        ) from exc

    reader = PdfReader(io.BytesIO(content), strict=False)
    pages: list[str] = []
    for page in reader.pages:
        try:
            t = page.extract_text(extraction_mode=extraction_mode) or ""  # type: ignore[arg-type]
        except Exception:
            t = ""
        t = t.strip()
        if t:
            pages.append(t)
    return "\n\n".join(pages)


def _extract_pdf_text_pdfminer(content: bytes) -> str:
    try:
        from pdfminer.high_level import extract_text as pdfminer_extract  # type: ignore
    except ImportError:
        return ""

    try:
        return (pdfminer_extract(io.BytesIO(content)) or "").strip()
    except Exception:
        return ""


def _extract_pdf_text_from_bytes(content: bytes) -> str:
    """
    Text-only extraction from PDF (pypdf plain → pypdf layout → pdfminer.six).
    OCR / scanned pages are not supported — image-only PDFs return empty.
    """
    for mode in ("plain", "layout"):
        text = _extract_pdf_text_pypdf(content, extraction_mode=mode)
        if text.strip():
            return text

    fallback = _extract_pdf_text_pdfminer(content)
    if fallback:
        return fallback

    return ""


def _extract_docx_text_from_bytes(content: bytes) -> str:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "DOCX extraction requires the python-docx package (install backend requirements)."
        ) from exc

    doc = Document(io.BytesIO(content))
    parts = [p.text.strip() for p in doc.paragraphs if (p.text or "").strip()]
    return "\n".join(parts)


def extract_text_from_uploaded_bytes(filename: str, content: bytes) -> tuple[str, str]:
    """
    Returns (normalized_title, extracted_text)
    """
    ext = os.path.splitext(filename)[1].lower()
    title = os.path.splitext(os.path.basename(filename))[0].strip()
    if not title:
        title = "uploaded"

    if ext == ".csv":
        return title, extract_text_from_csv_bytes(content)
    if ext == ".txt":
        return title, _decode_csv_bytes(content).strip()
    if ext == ".pdf":
        return title, _extract_pdf_text_from_bytes(content)
    if ext in {".docx"}:
        return title, _extract_docx_text_from_bytes(content)

    raise ValueError(f"Unsupported file type: {ext}")

