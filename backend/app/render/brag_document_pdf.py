"""PDF export for a completed Brag Document job — same Playwright/Chromium + Jinja2
pattern as render/pdf.py (see that module's docstring), rendering `templates/
brag_document.html` instead of `project.html`. The browser instance is the one launched
once in app/main.py's lifespan handler and reused across requests.
"""

from jinja2 import Environment, PackageLoader, select_autoescape
from playwright.async_api import Browser

from app.models.brag_document_job import BragDocumentJob

_env = Environment(
    loader=PackageLoader("app.render", "templates"),
    autoescape=select_autoescape(["html"]),
)


def render_brag_document_html(job: BragDocumentJob) -> str:
    template = _env.get_template("brag_document.html")
    return template.render(job=job, result=job.result or {}, stats=job.hour_stats or {})


async def render_brag_document_pdf(browser: Browser, job: BragDocumentJob) -> bytes:
    html = render_brag_document_html(job)
    page = await browser.new_page()
    try:
        await page.set_content(html, wait_until="networkidle")
        return await page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "20mm", "bottom": "20mm", "left": "18mm", "right": "18mm"},
        )
    finally:
        await page.close()
