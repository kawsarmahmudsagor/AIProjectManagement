"""Document ingest: magic-byte format detection, parsing, and the scanned-PDF pre-flight
check (backend/DESIGN.md §5, docs/RESEARCH.md §C).

Format is detected by magic bytes, never by file extension — a renamed .doc masquerading
as .docx must fail with a clear message, not a cryptic zipfile error deep inside
python-docx. Legacy binary .doc is rejected outright: LibreOffice headless is the only
thing that actually converts it on Windows and a 700MB dependency isn't worth it for a
19-year-obsolete format (docs/RESEARCH.md §C3).
"""

import io
from dataclasses import dataclass

import pdfplumber
from docx2python import docx2python

PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"  # .docx is a zip container
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # legacy .doc / .xls / .ppt

_SCANNED_PDF_CHAR_THRESHOLD = 100


class UnsupportedFormatError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class IngestResult:
    raw_bytes: bytes
    mime_type: str
    extracted_text: str | None
    page_count: int | None
    is_scanned: bool
    filename: str


def sniff_mime_type(data: bytes, filename: str) -> str:
    if data.startswith(PDF_MAGIC):
        return "application/pdf"
    if data.startswith(ZIP_MAGIC):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if data.startswith(OLE2_MAGIC):
        raise UnsupportedFormatError(
            "legacy_format_unsupported",
            f"{filename} is a legacy .doc-family file we can't read reliably. Please "
            "open it in Word, Google Docs, or LibreOffice and save as .docx or export as "
            "PDF, then upload again.",
        )
    # Fall back to a plain-text guess: anything that decodes cleanly as UTF-8 with no
    # NUL bytes is treated as .txt/.md.
    try:
        data.decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError as exc:
        raise UnsupportedFormatError(
            "unrecognized_format",
            f"{filename} isn't a PDF, DOCX, or text file we recognize.",
        ) from exc


def _extract_pdf(data: bytes) -> tuple[str, int]:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            text_parts.append(page.extract_text() or "")
    return "\n\n".join(text_parts), page_count


def _extract_docx(data: bytes) -> str:
    # docx2python catches headers/footers/text boxes that bare python-docx misses — document
    # templates frequently put key details in a header (docs/RESEARCH.md §C2).
    result = docx2python(io.BytesIO(data))
    try:
        return result.text
    finally:
        result.close()


def ingest(data: bytes, filename: str) -> IngestResult:
    mime_type = sniff_mime_type(data, filename)

    if mime_type == "application/pdf":
        text, page_count = _extract_pdf(data)
        is_scanned = len(text.strip()) < _SCANNED_PDF_CHAR_THRESHOLD
        return IngestResult(
            raw_bytes=data,
            mime_type=mime_type,
            extracted_text=text or None,
            page_count=page_count,
            is_scanned=is_scanned,
            filename=filename,
        )

    if mime_type.endswith("wordprocessingml.document"):
        text = _extract_docx(data)
        return IngestResult(
            raw_bytes=data,
            mime_type=mime_type,
            extracted_text=text,
            page_count=None,
            is_scanned=False,
            filename=filename,
        )

    # text/plain
    text = data.decode("utf-8")
    return IngestResult(
        raw_bytes=data,
        mime_type=mime_type,
        extracted_text=text,
        page_count=None,
        is_scanned=False,
        filename=filename,
    )
