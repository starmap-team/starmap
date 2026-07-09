"""Unit tests for app.services.resume_service — resume parsing and extraction."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.resume_service import (
    SUPPORTED_RESUME_EXTENSIONS,
    _decode_text,
    _extract_docx_text,
    _extract_pdf_text,
    ensure_supported_resume,
    extract_resume_text,
    get_resume_extension,
    run_resume_extraction,
)

# ---------------------------------------------------------------------------
# get_resume_extension
# ---------------------------------------------------------------------------


class TestGetResumeExtension:
    def test_pdf(self):
        assert get_resume_extension("resume.pdf") == "pdf"

    def test_docx(self):
        assert get_resume_extension("resume.docx") == "docx"

    def test_uppercase(self):
        assert get_resume_extension("RESUME.PDF") == "pdf"

    def test_mixed_case(self):
        assert get_resume_extension("Resume.DocX") == "docx"

    def test_multiple_dots(self):
        assert get_resume_extension("my.cool.resume.pdf") == "pdf"

    def test_no_extension(self):
        with pytest.raises(ValueError, match="must include an extension"):
            get_resume_extension("resume")

    def test_empty(self):
        with pytest.raises(ValueError, match="must include an extension"):
            get_resume_extension("")

    def test_trailing_dot_returns_empty_string(self):
        """A filename ending with '.' passes the '.' check and returns ''."""
        assert get_resume_extension("resume.") == ""


# ---------------------------------------------------------------------------
# ensure_supported_resume
# ---------------------------------------------------------------------------


class TestEnsureSupportedResume:
    def test_pdf_supported(self):
        assert ensure_supported_resume("test.pdf") == "pdf"

    def test_docx_supported(self):
        assert ensure_supported_resume("test.docx") == "docx"

    def test_doc_rejected_b24(self) -> None:
        # B24: legacy .doc binary format cannot be parsed reliably
        # without antiword/LibreOffice; ensure_supported_resume must reject
        # it so callers get a clear 4xx instead of garbage.
        with pytest.raises(ValueError, match="Unsupported file type: .doc"):
            ensure_supported_resume("test.doc")

    def test_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type: .xyz"):
            ensure_supported_resume("test.xyz")

    def test_unsupported_shows_supported_list(self):
        # B24: .doc removed — list is now .docx, .pdf only
        with pytest.raises(ValueError, match=r"\.docx.*\.pdf"):
            ensure_supported_resume("test.png")


# ---------------------------------------------------------------------------
# _decode_text
# ---------------------------------------------------------------------------


class TestDecodeText:
    def test_utf8(self):
        text = _decode_text(b"Hello World")
        assert text == "Hello World"

    def test_gbk(self):
        text = _decode_text("你好世界".encode("gbk"))
        assert text == "你好世界"

    def test_utf16(self):
        text = _decode_text("Hello".encode("utf-16"))
        assert text == "Hello"

    def test_latin1(self):
        text = _decode_text("cafeé".encode("latin-1"))
        assert text == "cafeé"

    def test_ignore_errors_fallback(self):
        """Garbage bytes should fall through to utf-8 with ignore."""
        text = _decode_text(b"\xff\xfe\x00\x01")
        # Should not raise; returns whatever utf-8 ignore gives back
        assert isinstance(text, str)

    def test_blank_bytes_returns_empty(self):
        text = _decode_text(b"")
        assert text == ""


# ---------------------------------------------------------------------------
# _extract_pdf_text
# ---------------------------------------------------------------------------


class TestExtractPdfText:
    def test_non_pdf_bytes_falls_back_to_decode(self):
        """When pdfplumber fails, fall back to raw decode."""
        text = _extract_pdf_text(b"Hello plain text in pdf wrapper")
        assert "Hello plain text" in text

    def test_empty_bytes(self):
        text = _extract_pdf_text(b"")
        assert text == ""

    def test_pdfplumber_successful_extraction(self):
        """When pdfplumber opens successfully, return extracted page text."""
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_page.text = "ignored"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page]

        with patch("app.services.resume_service.pdfplumber.open", return_value=mock_pdf) as mock_open:
            # We need to make the context manager work
            mock_pdf_cm = MagicMock()
            mock_pdf_cm.__enter__.return_value = mock_pdf
            mock_open.return_value = mock_pdf_cm

            text = _extract_pdf_text(b"fake pdf bytes")

        assert "Page 1 content" in text

    def test_pdfplumber_multiple_pages(self):
        """Multiple pages should be joined with newlines."""
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page 1"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page 2"
        mock_pdf = MagicMock()
        mock_pdf.pages = [mock_page1, mock_page2]

        with patch("app.services.resume_service.pdfplumber.open") as mock_open:
            mock_pdf_cm = MagicMock()
            mock_pdf_cm.__enter__.return_value = mock_pdf
            mock_open.return_value = mock_pdf_cm

            text = _extract_pdf_text(b"fake pdf bytes")

        assert "Page 1" in text
        assert "Page 2" in text


# ---------------------------------------------------------------------------
# _extract_docx_text
# ---------------------------------------------------------------------------


class TestExtractDocxText:
    def test_non_docx_bytes_falls_back_to_decode(self):
        """When docx parser fails, fall back to raw decode."""
        text = _extract_docx_text(b"Hello plain text in docx wrapper")
        assert "Hello plain text" in text

    def test_empty_bytes(self):
        text = _extract_docx_text(b"")
        assert text == ""

    def test_docx_paragraphs_and_tables(self):
        """Should extract both paragraph text and table cell text."""
        mock_para1 = MagicMock()
        mock_para1.text = "  Hello  "
        mock_para2 = MagicMock()
        mock_para2.text = "  "
        mock_para3 = MagicMock()
        mock_para3.text = "World"

        mock_cell1 = MagicMock()
        mock_cell1.text = "Skill"
        mock_cell2 = MagicMock()
        mock_cell2.text = "Level"
        mock_cell3 = MagicMock()
        mock_cell3.text = ""
        mock_row = MagicMock()
        mock_row.cells = [mock_cell1, mock_cell2, mock_cell3]

        mock_table = MagicMock()
        mock_table.rows = [mock_row]

        mock_document = MagicMock()
        mock_document.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_document.tables = [mock_table]

        with patch("app.services.resume_service.Document", return_value=mock_document):
            text = _extract_docx_text(b"fake docx bytes")

        assert "Hello" in text
        assert "World" in text
        assert "Skill | Level" in text


# ---------------------------------------------------------------------------
# extract_resume_text
# ---------------------------------------------------------------------------


class TestExtractResumeText:
    def test_pdf_plain_text_fallback(self):
        """Plain text bytes with .pdf extension fall back to decode."""
        text = extract_resume_text("test.pdf", b"Hello World Resume Content")
        assert "Hello World Resume" in text

    def test_docx_extension(self):
        text = extract_resume_text("test.docx", b"Plain DOCX content")
        assert "Plain DOCX content" in text

    def test_doc_rejected_b24(self) -> None:
        # B24: legacy .doc binary format is no longer accepted. The
        # ValueError raised by ensure_supported_resume() carries through
        # from extract_resume_text — no silent garbage fallback.
        with pytest.raises(ValueError, match="Unsupported file type: .doc"):
            extract_resume_text("test.doc", b"Plain DOC content")

    def test_empty_content_raises(self):
        with pytest.raises(ValueError, match="contains no extractable text"):
            extract_resume_text("test.pdf", b"")

    def test_unsupported_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported file type"):
            extract_resume_text("test.xyz", b"content")

    def test_docx_gbk_encoded(self):
        """DOCX fallback should handle GBK encoded content."""
        text = extract_resume_text("test.docx", "简历内容".encode("gbk"))
        assert "简历内容" in text

    def test_doc_rejected_extract_b24(self) -> None:
        """B24: ensure_supported_resume now rejects .doc up-front.

        Both legacy test inputs are exercised here to lock down the new
        contract: callers receive a ValueError instead of silently garbage.
        """
        with pytest.raises(ValueError, match="Unsupported file type: .doc"):
            extract_resume_text("test.doc", b"Some doc content here")
        with pytest.raises(ValueError, match="Unsupported file type: .doc"):
            with patch(
                "app.services.resume_service._extract_docx_text", return_value=""
            ), patch(
                "app.services.resume_service._decode_text", return_value="Fallback text"
            ):
                extract_resume_text("test.doc", b"some bytes")

    def test_unknown_extension_bypassing_validation(self):
        """The else-branch (fallback decode) via mock bypass of ensure_supported_resume."""
        with patch("app.services.resume_service.ensure_supported_resume", return_value="unknown"), \
             patch("app.services.resume_service._decode_text", return_value="Raw decode text"):
            text = extract_resume_text("test.unknown", b"some bytes")
        assert text == "Raw decode text"


# ---------------------------------------------------------------------------
# run_resume_extraction
# ---------------------------------------------------------------------------


class TestRunResumeExtraction:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Should extract text and call extract_from_jd."""
        mock_extract = AsyncMock(return_value={"success": True, "data": {"position_name": "Engineer"}})

        with patch("app.services.resume_service.extract_from_jd", mock_extract):
            result = await run_resume_extraction("test.pdf", b"John Doe Resume PDF content")

        assert result == {"success": True, "data": {"position_name": "Engineer"}}
        mock_extract.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_options(self):
        """Should merge user options with default source=resume."""
        mock_extract = AsyncMock(return_value={"success": True, "data": {}})

        with patch("app.services.resume_service.extract_from_jd", mock_extract):
            await run_resume_extraction(
                "test.docx",
                b"Resume content",
                options={"anti_hallucination_enabled": False},
            )

        _call_args = mock_extract.await_args
        assert _call_args is not None
        _kwargs = _call_args[1]
        assert _kwargs["options"] == {"source": "resume", "anti_hallucination_enabled": False}

    @pytest.mark.asyncio
    async def test_default_source_is_resume(self):
        """Should set source=resume when no options given."""
        mock_extract = AsyncMock(return_value={"success": True, "data": {}})

        with patch("app.services.resume_service.extract_from_jd", mock_extract):
            await run_resume_extraction("test.pdf", b"Content")

        _call_args = mock_extract.await_args
        assert _call_args is not None
        assert _call_args[1]["options"] == {"source": "resume"}

    @pytest.mark.asyncio
    async def test_empty_content_raises(self):
        """Should raise when resume text is empty."""
        with pytest.raises(ValueError, match="contains no extractable text"):
            await run_resume_extraction("test.pdf", b"")

    @pytest.mark.asyncio
    async def test_unsupported_extension_raises(self):
        """Should raise for unsupported file types."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            await run_resume_extraction("test.xyz", b"content")

    @pytest.mark.asyncio
    async def test_user_options_override_source(self):
        """User options should override source key."""
        mock_extract = AsyncMock(return_value={"success": True, "data": {}})

        with patch("app.services.resume_service.extract_from_jd", mock_extract):
            await run_resume_extraction(
                "test.pdf",
                b"Content",
                options={"source": "custom_source"},
            )

        _call_args = mock_extract.await_args
        assert _call_args is not None
        assert _call_args[1]["options"]["source"] == "custom_source"


# ---------------------------------------------------------------------------
# SUPPORTED_RESUME_EXTENSIONS
# ---------------------------------------------------------------------------


def test_supported_extensions_drops_doc_b24():
    # B24: .doc binary format is no longer in the whitelist.
    assert "pdf" in SUPPORTED_RESUME_EXTENSIONS
    assert "docx" in SUPPORTED_RESUME_EXTENSIONS
    assert "doc" not in SUPPORTED_RESUME_EXTENSIONS
