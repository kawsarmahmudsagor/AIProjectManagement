import re

from playwright.async_api import Browser

from app.models.project import Project
from app.render.docx import render_project_docx
from app.render.pdf import render_project_pdf

_SLUG_RE = re.compile(r"[^A-Za-z0-9 _-]+")


def export_filename(project: Project, ext: str) -> str:
    safe = _SLUG_RE.sub("", project.name).strip().replace(" ", "-") or "project"
    return f"{safe}.{ext}"


async def export_project(project: Project, fmt: str, browser: Browser | None) -> tuple[bytes, str, str]:
    """Returns (bytes, content_type, filename)."""
    if fmt == "docx":
        content = render_project_docx(project)
        return (
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            export_filename(project, "docx"),
        )
    if fmt == "pdf":
        if browser is None:
            raise RuntimeError("PDF renderer (Playwright browser) is not initialized")
        content = await render_project_pdf(browser, project)
        return content, "application/pdf", export_filename(project, "pdf")
    raise ValueError(f"Unsupported export format: {fmt}")
