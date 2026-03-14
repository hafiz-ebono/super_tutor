"""Unit tests for extract_document() — TDD RED phase."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from app.extraction.document_extractor import (
    extract_document,
    DocumentExtractionError,
    TRUNCATION_LIMIT,
    TRUNCATION_MARKER,
    SCANNED_PDF_THRESHOLD,
)


# ---------------------------------------------------------------------------
# DocumentExtractionError
# ---------------------------------------------------------------------------

class TestDocumentExtractionError:
    def test_error_kind_attribute_accessible(self):
        """error_kind attribute must be accessible on the exception."""
        err = DocumentExtractionError(error_kind="scanned_pdf")
        assert err.error_kind == "scanned_pdf"

    def test_inherits_from_exception(self):
        """DocumentExtractionError must inherit from Exception."""
        err = DocumentExtractionError(error_kind="unsupported_format")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self):
        """Must be raiseable and catchable."""
        with pytest.raises(DocumentExtractionError) as exc_info:
            raise DocumentExtractionError(error_kind="scanned_pdf", message="No text")
        assert exc_info.value.error_kind == "scanned_pdf"

    def test_str_representation(self):
        """str(error) should include the message or kind."""
        err = DocumentExtractionError(error_kind="scanned_pdf", message="Scanned!")
        assert "Scanned!" in str(err)

    def test_default_message_falls_back_to_kind(self):
        """When no message given, str(error) should contain the kind."""
        err = DocumentExtractionError(error_kind="unsupported_format")
        assert "unsupported_format" in str(err)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_scanned_pdf_threshold_is_200(self):
        assert SCANNED_PDF_THRESHOLD == 200

    def test_truncation_limit_is_50000(self):
        assert TRUNCATION_LIMIT == 50_000

    def test_truncation_marker_content(self):
        assert "50,000" in TRUNCATION_MARKER
        assert "truncated" in TRUNCATION_MARKER.lower()


# ---------------------------------------------------------------------------
# Unsupported format
# ---------------------------------------------------------------------------

class TestUnsupportedFormat:
    def test_raises_for_txt_extension(self):
        """Unsupported extensions must raise DocumentExtractionError."""
        with pytest.raises(DocumentExtractionError) as exc_info:
            extract_document(b"some bytes", "file.txt")
        assert exc_info.value.error_kind == "unsupported_format"

    def test_raises_for_pptx_extension(self):
        with pytest.raises(DocumentExtractionError) as exc_info:
            extract_document(b"some bytes", "presentation.pptx")
        assert exc_info.value.error_kind == "unsupported_format"

    def test_raises_for_no_extension(self):
        with pytest.raises(DocumentExtractionError) as exc_info:
            extract_document(b"some bytes", "noextension")
        assert exc_info.value.error_kind == "unsupported_format"


# ---------------------------------------------------------------------------
# PDF extraction (mocked pypdf)
# ---------------------------------------------------------------------------

class TestPdfExtraction:
    def _make_mock_reader(self, page_texts: list[str]):
        """Build a mock PdfReader with pages returning given texts."""
        pages = []
        for text in page_texts:
            page = MagicMock()
            page.extract_text.return_value = text
            pages.append(page)
        reader = MagicMock()
        reader.pages = pages
        return reader

    @patch("app.extraction.document_extractor.PdfReader")
    def test_text_pdf_returns_extracted_text(self, mock_reader_cls):
        """Text-based PDF should return cleaned plain text."""
        long_enough = "A" * 300
        mock_reader_cls.return_value = self._make_mock_reader([long_enough])
        result, was_truncated = extract_document(b"fake_pdf", "file.pdf")
        assert isinstance(result, str)
        assert len(result) >= 200
        assert was_truncated is False

    @patch("app.extraction.document_extractor.PdfReader")
    def test_scanned_pdf_raises_error(self, mock_reader_cls):
        """PDF with <200 chars extracted must raise DocumentExtractionError(scanned_pdf)."""
        mock_reader_cls.return_value = self._make_mock_reader(["tiny"])
        with pytest.raises(DocumentExtractionError) as exc_info:
            extract_document(b"fake_pdf", "file.pdf")
        assert exc_info.value.error_kind == "scanned_pdf"

    @patch("app.extraction.document_extractor.PdfReader")
    def test_scanned_pdf_threshold_uses_stripped_length(self, mock_reader_cls):
        """Scanned-PDF detection must use stripped text length."""
        # 199 spaces — stripped = 0 chars → should raise
        mock_reader_cls.return_value = self._make_mock_reader([" " * 199])
        with pytest.raises(DocumentExtractionError) as exc_info:
            extract_document(b"fake_pdf", "file.pdf")
        assert exc_info.value.error_kind == "scanned_pdf"

    @patch("app.extraction.document_extractor.PdfReader")
    def test_none_page_text_treated_as_empty(self, mock_reader_cls):
        """page.extract_text() returning None must not crash extraction."""
        page_none = MagicMock()
        page_none.extract_text.return_value = None
        page_text = MagicMock()
        page_text.extract_text.return_value = "A" * 300
        reader = MagicMock()
        reader.pages = [page_none, page_text]
        mock_reader_cls.return_value = reader
        result, _ = extract_document(b"fake_pdf", "file.pdf")
        assert "A" * 10 in result  # At least part of the text is present

    @patch("app.extraction.document_extractor.PdfReader")
    def test_pdf_case_insensitive_extension(self, mock_reader_cls):
        """.PDF (uppercase) should be handled the same as .pdf."""
        long_enough = "B" * 300
        mock_reader_cls.return_value = self._make_mock_reader([long_enough])
        result, _ = extract_document(b"fake_pdf", "file.PDF")
        assert isinstance(result, str)

    @patch("app.extraction.document_extractor.PdfReader")
    def test_multi_page_pdf_combines_text(self, mock_reader_cls):
        """Multi-page PDF text should be combined from all pages."""
        mock_reader_cls.return_value = self._make_mock_reader(
            ["Page one " * 30, "Page two " * 30]
        )
        result, _ = extract_document(b"fake_pdf", "file.pdf")
        assert "Page one" in result
        assert "Page two" in result

    @patch("app.extraction.document_extractor.PdfReader")
    def test_pdf_uses_bytesio_not_disk(self, mock_reader_cls):
        """PdfReader must be called with a BytesIO object, not a path."""
        from io import BytesIO
        long_enough = "C" * 300
        mock_reader_cls.return_value = self._make_mock_reader([long_enough])
        extract_document(b"fake_pdf", "file.pdf")
        call_arg = mock_reader_cls.call_args[0][0]
        assert isinstance(call_arg, BytesIO)


# ---------------------------------------------------------------------------
# DOCX extraction (mocked python-docx)
# ---------------------------------------------------------------------------

class TestDocxExtraction:
    def _make_mock_doc(self, para_texts: list[str], table_cell_texts: list[str] = None):
        """Build a mock Document with given paragraph texts and optional table cells."""
        doc = MagicMock()
        paras = []
        for text in para_texts:
            para = MagicMock()
            para.text = text
            paras.append(para)
        doc.paragraphs = paras

        if table_cell_texts:
            cell = MagicMock()
            cell.text = table_cell_texts[0]
            row = MagicMock()
            row.cells = [cell]
            table = MagicMock()
            table.rows = [row]
            doc.tables = [table]
        else:
            doc.tables = []
        return doc

    @patch("app.extraction.document_extractor.Document")
    def test_docx_returns_paragraph_text(self, mock_doc_cls):
        """DOCX extraction must include paragraph text."""
        mock_doc_cls.return_value = self._make_mock_doc(["Para one.", "Para two."])
        result, _ = extract_document(b"fake_docx", "file.docx")
        assert "Para one" in result
        assert "Para two" in result

    @patch("app.extraction.document_extractor.Document")
    def test_docx_returns_table_cell_text(self, mock_doc_cls):
        """DOCX extraction must include table cell text."""
        mock_doc_cls.return_value = self._make_mock_doc(
            ["Intro paragraph."],
            table_cell_texts=["Cell content here."]
        )
        result, _ = extract_document(b"fake_docx", "file.docx")
        assert "Intro paragraph" in result
        assert "Cell content here" in result

    @patch("app.extraction.document_extractor.Document")
    def test_docx_skips_empty_paragraphs(self, mock_doc_cls):
        """Empty/whitespace-only paragraphs must be excluded."""
        mock_doc_cls.return_value = self._make_mock_doc(
            ["Real content.", "", "   ", "More content."]
        )
        result, _ = extract_document(b"fake_docx", "file.docx")
        assert "Real content" in result
        assert "More content" in result

    @patch("app.extraction.document_extractor.Document")
    def test_docx_uses_bytesio_not_disk(self, mock_doc_cls):
        """Document must be called with a BytesIO object, not a path."""
        from io import BytesIO
        mock_doc_cls.return_value = self._make_mock_doc(["Content here."])
        extract_document(b"fake_docx", "file.docx")
        call_arg = mock_doc_cls.call_args[0][0]
        assert isinstance(call_arg, BytesIO)

    @patch("app.extraction.document_extractor.Document")
    def test_docx_case_insensitive_extension(self, mock_doc_cls):
        """.DOCX (uppercase) should be handled the same as .docx."""
        mock_doc_cls.return_value = self._make_mock_doc(["Content."])
        result, _ = extract_document(b"fake_docx", "file.DOCX")
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    @patch("app.extraction.document_extractor.PdfReader")
    def test_pdf_text_truncated_at_50000_chars(self, mock_reader_cls):
        """PDF text exceeding 50,000 chars must be truncated with marker appended."""
        # Construct text with a paragraph boundary before TRUNCATION_LIMIT
        chunk = "A" * 1000 + "\n\n"  # 1002 chars per chunk
        long_text = chunk * 60  # ~60,000 chars
        page = MagicMock()
        page.extract_text.return_value = long_text
        reader = MagicMock()
        reader.pages = [page]
        mock_reader_cls.return_value = reader
        result, was_truncated = extract_document(b"fake_pdf", "file.pdf")
        assert TRUNCATION_MARKER.strip() in result
        assert len(result) < len(long_text)
        assert was_truncated is True

    @patch("app.extraction.document_extractor.Document")
    def test_docx_text_truncated_at_50000_chars(self, mock_doc_cls):
        """DOCX text exceeding 50,000 chars must be truncated with marker appended."""
        long_para = "B" * 1000
        paras = [long_para] * 60  # 60,000 chars
        doc = MagicMock()
        para_mocks = []
        for t in paras:
            p = MagicMock()
            p.text = t
            para_mocks.append(p)
        doc.paragraphs = para_mocks
        doc.tables = []
        mock_doc_cls.return_value = doc
        result, was_truncated = extract_document(b"fake_docx", "file.docx")
        assert TRUNCATION_MARKER.strip() in result
        assert was_truncated is True

    @patch("app.extraction.document_extractor.PdfReader")
    def test_truncation_marker_content_visible(self, mock_reader_cls):
        """Truncation marker must contain the 50,000 char reference."""
        chunk = "C" * 999 + "\n\n"
        long_text = chunk * 60
        page = MagicMock()
        page.extract_text.return_value = long_text
        reader = MagicMock()
        reader.pages = [page]
        mock_reader_cls.return_value = reader
        result, _ = extract_document(b"fake_pdf", "file.pdf")
        assert "50,000" in result

    @patch("app.extraction.document_extractor.PdfReader")
    def test_short_text_not_truncated(self, mock_reader_cls):
        """Text below TRUNCATION_LIMIT must not have the truncation marker."""
        text = "D" * 300
        page = MagicMock()
        page.extract_text.return_value = text
        reader = MagicMock()
        reader.pages = [page]
        mock_reader_cls.return_value = reader
        result, was_truncated = extract_document(b"fake_pdf", "file.pdf")
        assert "truncated" not in result.lower()
        assert was_truncated is False
