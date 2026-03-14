"""
Memory-only document text extraction for PDF and DOCX files.

Never writes to the filesystem. Uses BytesIO throughout.
Raises DocumentExtractionError for unrecoverable conditions.

Phase 12 wraps calls to extract_document() with asyncio.to_thread()
since pypdf and python-docx are blocking synchronous libraries.
"""
from io import BytesIO
import logging

from pypdf import PdfReader
from docx import Document

from app.extraction.cleaner import clean_extracted_content

logger = logging.getLogger("super_tutor.extraction")

SCANNED_PDF_THRESHOLD = 200  # minimum chars (stripped) to consider a PDF text-based
TRUNCATION_LIMIT = 50_000
TRUNCATION_MARKER = (
    "\n\n[Content truncated: document exceeds 50,000 characters. "
    "Upload a specific chapter or section for full coverage.]"
)


class DocumentExtractionError(Exception):
    """Raised for unrecoverable document extraction failures."""

    def __init__(self, error_kind: str, message: str = ""):
        self.error_kind = error_kind
        self.message = message
        super().__init__(message or error_kind)


def extract_document(data: bytes, filename: str) -> str:
    """
    Extract plain text from PDF or DOCX bytes.

    Args:
        data: Raw file bytes.
        filename: Original filename — used for extension-based dispatch.

    Returns:
        Cleaned, possibly-truncated plain text.

    Raises:
        DocumentExtractionError: For scanned PDFs, unsupported formats.
    """
    fname = filename.lower()
    if fname.endswith(".pdf"):
        raw = _extract_pdf(data)
    elif fname.endswith(".docx"):
        raw = _extract_docx(data)
    else:
        raise DocumentExtractionError(
            error_kind="unsupported_format",
            message=f"Unsupported file type: {filename}. Supported: PDF, DOCX.",
        )

    # Soft truncation before cleaning (truncation marker must survive cleaning)
    truncated = _soft_truncate(raw)

    return clean_extracted_content(truncated, source_type="document")


def _extract_pdf(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf. Raises for scanned/image PDFs."""
    reader = PdfReader(BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        parts.append(text)
    raw = "\n\n".join(parts)

    if len(raw.strip()) < SCANNED_PDF_THRESHOLD:
        raise DocumentExtractionError(
            error_kind="scanned_pdf",
            message=(
                "This PDF appears to be scanned or image-based. "
                "No readable text could be extracted."
            ),
        )
    return raw


def _extract_docx(docx_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx.

    Extracts non-empty paragraphs and table cells.
    Note: merged cells in complex tables may produce duplicate text;
    deduplicate by cell identity if this becomes an issue in production.
    """
    doc = Document(BytesIO(docx_bytes))
    parts: list[str] = []

    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    parts.append(cell.text)

    return "\n\n".join(parts)


def _soft_truncate(text: str) -> str:
    """Truncate text at the nearest paragraph or sentence boundary below TRUNCATION_LIMIT."""
    if len(text) <= TRUNCATION_LIMIT:
        return text

    # Prefer paragraph boundary
    boundary = text.rfind("\n\n", 0, TRUNCATION_LIMIT)
    if boundary == -1:
        # Fall back to sentence boundary
        boundary = text.rfind(". ", 0, TRUNCATION_LIMIT)
    if boundary == -1:
        # Hard cut as last resort
        boundary = TRUNCATION_LIMIT

    logger.warning(
        "Document truncated at char %d (original length: %d)",
        boundary,
        len(text),
    )
    return text[:boundary] + TRUNCATION_MARKER
