"""Mirrors services/export_service.py's (bytes, content_type, filename) return shape for
the Brag Document feature's docx/pdf export endpoint.
"""

import re

from playwright.async_api import Browser

from app.models.brag_document_job import BragDocumentJob
from app.render.brag_document_docx import render_brag_document_docx
from app.render.brag_document_pdf import render_brag_document_pdf

_SLUG_RE = re.compile(r"[^A-Za-z0-9 _-]+")


def export_filename(job: BragDocumentJob, ext: str) -> str:
    safe = _SLUG_RE.sub("", job.name or f"{job.member_name}-{job.target_month}").strip().replace(" ", "-")
    return f"{safe or 'brag-document'}.{ext}"


async def export_brag_document(job: BragDocumentJob, fmt: str, browser: Browser | None) -> tuple[bytes, str, str]:
    """Returns (bytes, content_type, filename)."""
    if fmt == "docx":
        content = render_brag_document_docx(job)
        return (
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            export_filename(job, "docx"),
        )
    if fmt == "pdf":
        if browser is None:
            raise RuntimeError("PDF renderer (Playwright browser) is not initialized")
        content = await render_brag_document_pdf(browser, job)
        return content, "application/pdf", export_filename(job, "pdf")
    raise ValueError(f"Unsupported export format: {fmt}")
