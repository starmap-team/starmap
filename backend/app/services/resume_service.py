"""Resume parsing and extraction helpers for phase 4."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pdfplumber
from docx import Document
from loguru import logger

from app.core.extraction.jd_extract import extract_from_jd

SUPPORTED_RESUME_EXTENSIONS = {"pdf", "docx"}


def get_resume_extension(filename: str) -> str:
    """Return the lowercased file extension or raise for unsupported names."""
    if not filename or "." not in filename:
        raise ValueError("Resume filename must include an extension")
    return filename.rsplit(".", 1)[-1].lower()


def ensure_supported_resume(filename: str) -> str:
    """Validate the uploaded resume extension."""
    ext = get_resume_extension(filename)
    if ext not in SUPPORTED_RESUME_EXTENSIONS:
        supported = ", ".join(f".{item}" for item in sorted(SUPPORTED_RESUME_EXTENSIONS))
        raise ValueError(f"Unsupported file type: .{ext}. Supported: {supported}")
    return ext


def _decode_text(content_bytes: bytes) -> str:
    for encoding in ("utf-8", "gbk", "utf-16", "latin-1"):
        try:
            text = content_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
        if text.strip():
            return text
    return content_bytes.decode("utf-8", errors="ignore")


def _extract_pdf_text(content_bytes: bytes) -> str:
    pages: list[str] = []
    try:
        with pdfplumber.open(BytesIO(content_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text.strip())
    except Exception as exc:
        logger.warning("PDF parsing failed, fallback to raw decode: {}", exc)
    return "\n".join(pages).strip() or _decode_text(content_bytes).strip()


def _extract_docx_text(content_bytes: bytes) -> str:
    try:
        document = Document(BytesIO(content_bytes))
    except Exception as exc:
        logger.warning("DOCX parsing failed, fallback to raw decode: {}", exc)
        return _decode_text(content_bytes).strip()

    lines: list[str] = []
    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if text:
            lines.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))

    return "\n".join(lines).strip()


def extract_resume_text(filename: str, content_bytes: bytes) -> str:
    """Extract plaintext from supported resume formats."""
    ext = ensure_supported_resume(filename)

    if ext == "pdf":
        text = _extract_pdf_text(content_bytes)
    elif ext == "docx":
        text = _extract_docx_text(content_bytes)
    else:
        text = _decode_text(content_bytes).strip()

    if not text:
        raise ValueError("Resume file contains no extractable text")
    return text


async def run_resume_extraction(
    filename: str,
    content_bytes: bytes,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Parse a resume file and run the shared extraction pipeline."""
    text = extract_resume_text(filename, content_bytes)
    merged_options = {"source": "resume"}
    if options:
        merged_options.update(options)
    return await extract_from_jd(text, options=merged_options)
