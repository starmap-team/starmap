"""Unit tests for resume parsing service."""
from __future__ import annotations

import pytest

from app.services.resume_service import (
    SUPPORTED_RESUME_EXTENSIONS,
    ensure_supported_resume,
    extract_resume_text,
    get_resume_extension,
)


class TestGetResumeExtension:
    def test_pdf(self):
        assert get_resume_extension("resume.pdf") == "pdf"

    def test_docx(self):
        assert get_resume_extension("resume.docx") == "docx"

    def test_uppercase(self):
        assert get_resume_extension("RESUME.PDF") == "pdf"

    def test_no_extension(self):
        with pytest.raises(ValueError):
            get_resume_extension("resume")

    def test_empty(self):
        with pytest.raises(ValueError):
            get_resume_extension("")


class TestEnsureSupportedResume:
    def test_pdf_supported(self):
        assert ensure_supported_resume("test.pdf") == "pdf"

    def test_docx_supported(self):
        assert ensure_supported_resume("test.docx") == "docx"

    def test_unsupported(self):
        with pytest.raises(ValueError):
            ensure_supported_resume("test.xyz")


class TestExtractResumeText:
    def test_plain_text_via_pdf(self):
        # Plain text content - try as PDF, falls back to raw decode
        text = extract_resume_text("test.pdf", b"Hello World Resume Content")
        assert "Hello World Resume" in text

    def test_docx_extension(self):
        text = extract_resume_text("test.docx", b"Plain DOCX content")
        assert "Plain DOCX content" in text

    def test_doc_fallback(self):
        text = extract_resume_text("test.doc", b"Plain DOC content")
        assert "Plain DOC content" in text

    def test_empty_content(self):
        with pytest.raises(ValueError):
            extract_resume_text("test.pdf", b"")

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError):
            extract_resume_text("test.xyz", b"content")


def test_supported_extensions():
    assert "pdf" in SUPPORTED_RESUME_EXTENSIONS
    assert "docx" in SUPPORTED_RESUME_EXTENSIONS
