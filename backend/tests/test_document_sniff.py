"""sniff_mime_type's additive .xlsx branch (app/ingest/extract.py): confirms .docx
detection is completely unaffected and .xlsx is now recognized by inspecting which
internal OOXML part a zip container actually holds, rather than by file extension.
"""

import io
import zipfile

import pytest
from openpyxl import Workbook

from app.ingest.extract import (
    DOCX_MIME_TYPE,
    XLSX_MIME_TYPE,
    UnsupportedFormatError,
    sniff_mime_type,
)


def _minimal_docx_bytes() -> bytes:
    """A minimal, real zip container with only the one internal part sniff_mime_type
    actually looks for — not a full valid .docx, but enough to exercise the branch."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
    return buf.getvalue()


def _minimal_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    wb = Workbook()
    wb.active.title = "Sheet1"
    wb.save(buf)
    return buf.getvalue()


def test_docx_is_still_recognized():
    assert sniff_mime_type(_minimal_docx_bytes(), "resume.docx") == DOCX_MIME_TYPE


def test_real_xlsx_is_recognized():
    assert sniff_mime_type(_minimal_xlsx_bytes(), "standup.xlsx") == XLSX_MIME_TYPE


def test_zip_with_neither_known_part_falls_back_to_docx():
    """Preserves the exact pre-existing fallback behavior for any other zip shape —
    sniff_mime_type must not start rejecting something it used to accept."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("some/other/file.xml", "<root/>")
    assert sniff_mime_type(buf.getvalue(), "mystery.zip") == DOCX_MIME_TYPE


def test_pdf_and_txt_detection_unaffected():
    assert sniff_mime_type(b"%PDF-1.7 rest of file", "doc.pdf") == "application/pdf"
    assert sniff_mime_type(b"hello world", "notes.txt") == "text/plain"


def test_legacy_ole2_doc_is_rejected():
    ole2_bytes = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16
    with pytest.raises(UnsupportedFormatError) as exc_info:
        sniff_mime_type(ole2_bytes, "old.doc")
    assert exc_info.value.code == "legacy_format_unsupported"
