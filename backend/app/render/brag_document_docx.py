"""DOCX export for a completed Brag Document job — adapts the reference standup_cli
tool's `generate_brag_document_docx` (Calibri/heading-color conventions, same as this
app's own render/docx.py), with the "Usage Details" section removed entirely (plan
decision #4). Reads only `job.result` (LLM-authored prose) and `job.hour_stats`
(deterministic arithmetic) — the subtitle line is built from `hour_stats` only, never
from `result`, so a hallucinated hour figure could never reach an exported document.
"""

import io

from docx import Document
from docx.shared import Inches, Pt, RGBColor

from app.models.brag_document_job import BragDocumentJob

_TITLE_COLOR = RGBColor(0x1F, 0x49, 0x7D)
_SUBTITLE_COLOR = RGBColor(0x66, 0x66, 0x66)
_HEADING_COLOR = RGBColor(0x11, 0x11, 0x11)
_SUBHEADING_COLOR = RGBColor(0x22, 0x22, 0x22)
_BODY_COLOR = RGBColor(0x33, 0x33, 0x33)


def _add_heading(document: Document, text: str, *, size: int, space_before: int = 12, space_after: int = 4):
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(size)
    run.font.color.rgb = _HEADING_COLOR
    return p


def _add_subheading(document: Document, text: str, *, space_before: int = 6, space_after: int = 2):
    clean_text = (text or "").rstrip(":").strip()
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    run = p.add_run(clean_text)
    run.bold = True
    run.font.name = "Calibri"
    run.font.size = Pt(11.5)
    run.font.color.rgb = _SUBHEADING_COLOR
    return p


def _add_bullet(document: Document, text: str, *, indent: bool = False):
    p = document.add_paragraph(style="List Bullet 2" if indent else "List Bullet")
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(11)
    run.font.color.rgb = _BODY_COLOR
    return p


def _add_paragraph(document: Document, text: str, *, italic: bool = False):
    p = document.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.15
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(10.5)
    run.font.italic = italic
    run.font.color.rgb = _SUBTITLE_COLOR
    return p


def render_brag_document_docx(job: BragDocumentJob) -> bytes:
    result = job.result or {}
    stats = job.hour_stats or {}

    document = Document()
    for section in document.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    normal_font = document.styles["Normal"].font
    normal_font.name = "Calibri"
    normal_font.size = Pt(11)
    normal_font.color.rgb = _BODY_COLOR

    # 1. Title + subtitle (period/hours/sprints) — subtitle built from hour_stats only.
    title_p = document.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    r_title = title_p.add_run(f"Monthly Brag Document - {job.member_name}")
    r_title.bold = True
    r_title.font.name = "Calibri"
    r_title.font.size = Pt(16)
    r_title.font.color.rgb = _TITLE_COLOR

    sprints = ", ".join(w.split("(")[0].strip() for w in stats.get("included_weeks", []))
    total_hours = stats.get("total_hours", 0.0)
    sub_p = document.add_paragraph()
    sub_p.paragraph_format.space_before = Pt(0)
    sub_p.paragraph_format.space_after = Pt(14)
    r_sub = sub_p.add_run(
        f"Period: {job.target_month}  |  Total Logged Work: {total_hours:.1f} hrs  |  Sprints: {sprints}"
    )
    r_sub.font.italic = True
    r_sub.font.size = Pt(10)
    r_sub.font.color.rgb = _SUBTITLE_COLOR

    # 2. Work Accomplishments -> Technical Contribution (grouped by project)
    #    + Team Support & Collaboration. NO "Usage Details" section (plan decision #4).
    _add_heading(document, "Work Accomplishments", size=14, space_before=10)

    _add_heading(document, "Technical Contribution", size=12, space_before=6)
    tech_groups = result.get("technical_contributions") or []
    if tech_groups:
        for group in tech_groups:
            _add_subheading(document, group.get("project_name") or "On Demand / Miscellaneous")
            subsections = group.get("subsections") or []
            if subsections:
                for sub in subsections:
                    heading = sub.get("heading")
                    if heading:
                        _add_subheading(document, heading, space_before=4, space_after=1)
                    for bullet in sub.get("bullets") or []:
                        _add_bullet(document, bullet, indent=bool(heading))
            for bullet in group.get("bullets") or []:
                _add_bullet(document, bullet)
            key_contribution = group.get("key_contribution")
            if key_contribution:
                _add_paragraph(document, f"Key Contribution: {key_contribution}", italic=True)
    else:
        _add_bullet(document, "No technical contributions were found for this period.")

    overall_impact = result.get("overall_impact") or []
    if overall_impact:
        _add_heading(document, "Overall Impact", size=12, space_before=12)
        for area in overall_impact:
            category = area.get("category")
            summary = area.get("summary")
            if category and summary:
                _add_bullet(document, f"{category}: {summary}")

    _add_heading(document, "Team Support & Collaboration", size=12, space_before=12)
    support_bullets = result.get("team_support_bullets") or []
    if support_bullets:
        for bullet in support_bullets:
            _add_bullet(document, bullet)
    else:
        _add_bullet(document, "No team support activity was logged for this period.")

    # 3. Learning & Development
    _add_heading(document, "Learning & Development (L&D)", size=12, space_before=12)
    learning_bullets = result.get("learning_bullets") or []
    if learning_bullets:
        for bullet in learning_bullets:
            _add_bullet(document, bullet)
    else:
        _add_bullet(document, "No learning & development activity was logged for this period.")

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()
