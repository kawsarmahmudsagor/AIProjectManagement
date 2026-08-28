"""PDF export via Playwright/Chromium, not WeasyPrint — WeasyPrint still requires an
MSYS2 + Pango native install on Windows as of v69 (docs/RESEARCH.md §C5), a real
onboarding blocker for a Windows-first dev team. One Jinja2 template renders both the
on-screen preview and the PDF.

The browser instance is launched once in the FastAPI lifespan handler (app/main.py) and
reused across requests — cold-launching Chromium per export is what makes Playwright
*look* slow; kept warm it's fast (docs/RESEARCH.md §C5).
"""

from jinja2 import Environment, PackageLoader, select_autoescape
from playwright.async_api import Browser

from app.models.project import Project

_env = Environment(
    loader=PackageLoader("app.render", "templates"),
    autoescape=select_autoescape(["html"]),
)


def render_project_html(project: Project) -> str:
    template = _env.get_template("project.html")
    return template.render(project=project)


async def render_project_pdf(browser: Browser, project: Project) -> bytes:
    html = render_project_html(project)
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
