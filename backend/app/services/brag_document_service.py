"""Orchestrates one Brag Document job: parse the standup Excel workbook -> gather this
user's own Project/Task rows as grounding context -> provider call -> normalize -> persist.

Mirrors services/breakdown_service.py's shape and stage transitions (PARSING ->
EXTRACTING -> STRUCTURING -> SUCCEEDED/FAILED, committing at each step, outer
try/except -> _fail(..., "UNEXPECTED_ERROR", ...)) plus its one load-bearing extra
function: normalize_brag_document() must never raise, for the same reason
normalize_breakdown() doesn't — a job failing because the model returned one malformed
bullet is a worse outcome for the user than a job that quietly repaired it.

`_gather_projects_context`/`_gather_completed_tasks_context` mirror the exact SQLAlchemy
query shape agents/chat_tools.py's project_search/task_search use, but as plain function
calls here — this feature has no tool-calling agent loop (it's a single-shot background
job, like extract()/propose_breakdown(), not the interactive chatbot).
"""

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.brag_document_job import BragDocumentJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import AgentPersona, User
from app.providers.base import BragDocumentInput, ProviderError
from app.providers.registry import get_provider
from app.providers.schema_utils import inline_refs
from app.schemas.brag_document import (
    LLMBragDocumentResult,
    LLMBulletGroup,
    LLMImpactArea,
    LLMTechnicalContributionGroup,
)
from app.services.standup_excel_service import (
    MemberMonthlySummary,
    aggregate_member_month,
    parse_standup_workbook,
)

logger = logging.getLogger(__name__)

_BRAG_DOCUMENT_SCHEMA = inline_refs(LLMBragDocumentResult.model_json_schema())

# Same hazard class as breakdown_service.py's _UNSAFE_CHARS_RE — control chars, zero-width
# spaces/joiners, and bidi override/isolate codepoints that could make a bullet visually
# read differently than its actual text (docs/RESEARCH.md). Built from chr() codepoints
# rather than \u-escapes in a plain string literal, to sidestep any editor/terminal
# normalization of raw unicode escape sequences.
_UNSAFE_RANGES = [
    (0x00, 0x08), (0x0B, 0x0C), (0x0E, 0x1F),  # control chars, excluding \t\n\r
    (0x200B, 0x200F),  # zero-width space/joiners, LTR/RTL marks
    (0x202A, 0x202E),  # bidi embedding/override controls
    (0x2066, 0x2069),  # bidi isolate controls
    (0xFEFF, 0xFEFF),  # BOM / zero-width no-break space
]
_UNSAFE_CHARS_RE = re.compile(
    "[" + "".join(f"{chr(lo)}-{chr(hi)}" for lo, hi in _UNSAFE_RANGES) + "]"
)

def default_brag_document_name(target_month: str) -> str:
    """The default name a saved brag document gets when the user doesn't give it one of
    their own — used by both routers/brag_documents.py's create endpoint and
    agents/chat_tools.py's generate_brag_document tool, so a document created either way
    is named identically."""
    return f"{target_month} Brag Document"


_MAX_BULLET_LEN = 400
_MAX_PROJECT_NAME_LEN = 200
_MAX_GROUPS = 30
_MAX_BULLETS_PER_GROUP = 30
_MAX_TEAM_BULLETS = 30
_MAX_LEARNING_BULLETS = 30
_MAX_SUBSECTIONS_PER_GROUP = 10
_MAX_HEADING_LEN = 100
_MAX_KEY_CONTRIBUTION_LEN = 700
_MAX_IMPACT_AREAS = 10
_MAX_IMPACT_CATEGORY_LEN = 60

_ON_DEMAND_MISC = "On Demand / Miscellaneous"


def _sanitize(text: str) -> str:
    return _UNSAFE_CHARS_RE.sub("", text)


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip() + "…"


def _sanitize_bullet(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = _sanitize(value).strip()
    if not cleaned:
        return None
    if len(cleaned) > _MAX_BULLET_LEN:
        cleaned = _truncate_at_word(cleaned, _MAX_BULLET_LEN)
    return cleaned


def _sanitize_bullet_list(raw: object, cap: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw[:cap]:
        cleaned = _sanitize_bullet(item)
        if cleaned:
            out.append(cleaned)
    return out


def _sanitize_subsections(raw: object, notes: list[str], group_label: str) -> list[LLMBulletGroup]:
    if not isinstance(raw, list):
        return []
    subsections: list[LLMBulletGroup] = []
    for item in raw[:_MAX_SUBSECTIONS_PER_GROUP]:
        if not isinstance(item, dict):
            continue
        heading = _sanitize(str(item.get("heading") or "")).strip()
        if len(heading) > _MAX_HEADING_LEN:
            heading = _truncate_at_word(heading, _MAX_HEADING_LEN)
        bullets = _sanitize_bullet_list(item.get("bullets"), _MAX_BULLETS_PER_GROUP)
        if not bullets:
            continue
        if not heading:
            notes.append(f'Dropped an unnamed sub-theme under "{group_label}".')
            continue
        subsections.append(LLMBulletGroup(heading=heading, bullets=bullets))
    return subsections


def _sanitize_key_contribution(raw: object) -> str:
    if not isinstance(raw, str):
        return ""
    cleaned = _sanitize(raw).strip()
    if len(cleaned) > _MAX_KEY_CONTRIBUTION_LEN:
        cleaned = _truncate_at_word(cleaned, _MAX_KEY_CONTRIBUTION_LEN)
    return cleaned


def _sanitize_impact_areas(raw: object, notes: list[str]) -> list[LLMImpactArea]:
    if not isinstance(raw, list):
        return []
    areas: list[LLMImpactArea] = []
    for index, item in enumerate(raw[:_MAX_IMPACT_AREAS]):
        if not isinstance(item, dict):
            notes.append(f"Dropped one overall-impact area with an unexpected shape (item {index + 1}).")
            continue
        category = _sanitize(str(item.get("category") or "")).strip()[:_MAX_IMPACT_CATEGORY_LEN]
        summary = _sanitize_bullet(item.get("summary")) or ""
        if not category or not summary:
            notes.append("Dropped an overall-impact area missing a category or summary.")
            continue
        areas.append(LLMImpactArea(category=category, summary=summary))
    if isinstance(raw, list) and len(raw) > _MAX_IMPACT_AREAS:
        notes.append(f"Dropped {len(raw) - _MAX_IMPACT_AREAS} overall-impact area(s) over the {_MAX_IMPACT_AREAS}-area cap.")
    return areas


def normalize_brag_document(raw: dict) -> LLMBragDocumentResult:
    """Repairs a raw provider response into a valid LLMBragDocumentResult. Total, not
    partial, in the same sense as breakdown_service.normalize_breakdown(): a missing
    project_name falls back to "On Demand / Miscellaneous" rather than being dropped, a
    non-string bullet is dropped rather than stringified, a group with no content in
    either `bullets` or `subsections` is dropped, a duplicate project-name group
    (case-insensitive) is merged — bullets, subsections, and key_contribution all — rather
    than emitted twice, and every list is capped rather than rejected outright. Every
    repair records a confidence_note; nothing here ever raises."""
    notes: list[str] = []

    if not isinstance(raw, dict):
        raw = {}

    raw_groups = raw.get("technical_contributions")
    if not isinstance(raw_groups, list):
        raw_groups = []

    groups: list[LLMTechnicalContributionGroup] = []
    group_index_by_key: dict[str, int] = {}

    for index, item in enumerate(raw_groups[:_MAX_GROUPS]):
        if not isinstance(item, dict):
            notes.append(f"Dropped one technical contribution group with an unexpected shape (item {index + 1}).")
            continue

        project_name = _sanitize(str(item.get("project_name") or "")).strip()
        if not project_name:
            project_name = _ON_DEMAND_MISC
        if len(project_name) > _MAX_PROJECT_NAME_LEN:
            project_name = _truncate_at_word(project_name, _MAX_PROJECT_NAME_LEN)

        bullets = _sanitize_bullet_list(item.get("bullets"), _MAX_BULLETS_PER_GROUP)
        subsections = _sanitize_subsections(item.get("subsections"), notes, project_name)
        key_contribution = _sanitize_key_contribution(item.get("key_contribution"))
        if not bullets and not subsections:
            notes.append(f'Dropped an empty technical contribution group "{project_name}".')
            continue

        key = project_name.lower()
        if key in group_index_by_key:
            existing = groups[group_index_by_key[key]]
            existing.bullets.extend(bullets)
            existing.subsections.extend(subsections)
            if not existing.key_contribution:
                existing.key_contribution = key_contribution
            notes.append(f'Merged a duplicate technical contribution group "{project_name}".')
            continue

        group_index_by_key[key] = len(groups)
        groups.append(
            LLMTechnicalContributionGroup(
                project_name=project_name,
                bullets=bullets,
                subsections=subsections,
                key_contribution=key_contribution,
            )
        )

    if len(raw_groups) > _MAX_GROUPS:
        notes.append(f"Dropped {len(raw_groups) - _MAX_GROUPS} technical contribution group(s) over the 30-group cap.")

    team_support_bullets = _sanitize_bullet_list(raw.get("team_support_bullets"), _MAX_TEAM_BULLETS)
    learning_bullets = _sanitize_bullet_list(raw.get("learning_bullets"), _MAX_LEARNING_BULLETS)
    overall_impact = _sanitize_impact_areas(raw.get("overall_impact"), notes)

    raw_notes = raw.get("confidence_notes")
    if isinstance(raw_notes, list):
        for n in raw_notes[:10]:
            if isinstance(n, str) and n.strip():
                notes.append(_sanitize(n.strip())[:300])

    return LLMBragDocumentResult(
        technical_contributions=groups,
        team_support_bullets=team_support_bullets,
        learning_bullets=learning_bullets,
        overall_impact=overall_impact,
        confidence_notes=notes[:20],
    )


def _summary_to_hour_stats(summary: MemberMonthlySummary) -> dict:
    """Mirrors schemas.brag_document.HourStatsOut 1:1 — every value here is deterministic
    arithmetic from standup_excel_service.aggregate_member_month(), never LLM-authored."""
    return {
        "member_name": summary.member_name,
        "month_name": summary.month_name,
        "year": summary.year,
        "included_weeks": list(summary.included_weeks),
        "total_hours": summary.total_hours,
        "expected_target_hours": summary.expected_target_hours,
        "gross_base_hours": summary.gross_base_hours,
        "holiday_deducted_hours": summary.holiday_deducted_hours,
        "holiday_count": summary.holiday_count,
        "holiday_names": list(summary.holiday_names),
        "leave_count": summary.leave_count,
        "leave_hours": summary.leave_hours,
        "leave_dates": list(summary.leave_dates),
        "blocker_count": summary.blocker_count,
        "billable_hours": summary.billable_hours,
        "non_billable_hours": summary.non_billable_hours,
        "balance_hours": summary.balance_hours,
        "target_completion_pct": summary.target_completion_pct,
    }


def _work_log_entries(summary: MemberMonthlySummary) -> list[dict]:
    entries: list[dict] = []
    for day in summary.days:
        if day.is_leave or day.is_holiday:
            continue
        for t in day.tasks:
            entries.append(
                {
                    "date_label": day.full_date_label,
                    "category": t.category,
                    "task_name": t.task_name,
                    "is_billable": t.is_billable,
                }
            )
    return entries


async def _gather_projects_context(db: AsyncSession, user_id: UUID) -> list[dict]:
    """Same query shape as agents/chat_tools.py's project_search, minus the free-text
    filter (every project is small, single-user scale, so the whole list is stuffed into
    the prompt rather than searched) — see this module's docstring."""
    stmt = (
        select(Project)
        .where(Project.user_id == user_id)
        .order_by(Project.is_current.desc(), Project.start_date.desc())
    )
    projects = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "role": p.role,
            "technologies": p.technologies,
            "description_long_text": p.description_long_text,
            "description_short_text": p.description_short_text,
            "responsibilities_long_text": p.responsibilities_long_text,
            "responsibilities_short_text": p.responsibilities_short_text,
        }
        for p in projects
    ]


def _month_bounds(target_month: str) -> tuple[datetime, datetime] | tuple[None, None]:
    """Parses "August 2026" into a [start, end) UTC range. Returns (None, None) for an
    unparseable string rather than raising — the caller treats that as "no completed
    tasks context available", not a hard failure of the whole job."""
    try:
        start = datetime.strptime(target_month.strip(), "%B %Y").replace(tzinfo=UTC)
    except ValueError:
        return None, None
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(month=start.month + 1)
    return start, end


async def _gather_completed_tasks_context(db: AsyncSession, user_id: UUID, target_month: str) -> list[dict]:
    """Same query shape as agents/chat_tools.py's task_search, scoped to DONE tasks
    completed within the target calendar month — this feature's "include the user's Task
    rows completed within the target month as supplementary context" addition."""
    month_start, month_end = _month_bounds(target_month)
    if month_start is None:
        return []

    stmt = (
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.status == TaskStatus.DONE,
            Task.completed_at.is_not(None),
            Task.completed_at >= month_start,
            Task.completed_at < month_end,
        )
        .order_by(Task.completed_at)
    )
    tasks = list((await db.execute(stmt)).scalars().all())
    if not tasks:
        return []

    project_ids = {t.project_id for t in tasks}
    proj_stmt = select(Project.id, Project.name).where(Project.id.in_(project_ids))
    name_by_id = {row[0]: row[1] for row in (await db.execute(proj_stmt)).all()}

    return [
        {
            "id": str(t.id),
            "project_id": str(t.project_id),
            "project_name": name_by_id.get(t.project_id, "Unknown project"),
            "title": t.title,
            "description": t.description,
        }
        for t in tasks
    ]


async def _fail(db: AsyncSession, job: BragDocumentJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def run_brag_document_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(BragDocumentJob, job_id)
    if job is None:
        logger.error("brag document job %s not found", job_id)
        return

    document = await db.get(Document, job.document_id)
    if document is None:
        await _fail(db, job, "DOCUMENT_MISSING", "The uploaded spreadsheet is missing")
        return

    job.status = JobStatus.PARSING
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        try:
            data = Path(document.storage_path).read_bytes()
            workbook = parse_standup_workbook(data, document.filename)
        except OSError as exc:
            await _fail(db, job, "STORAGE_ERROR", f"Could not read the uploaded file: {exc}")
            return
        except Exception as exc:
            logger.exception("Failed to parse standup workbook for brag document job %s", job_id)
            await _fail(db, job, "PARSE_ERROR", f"Could not parse the uploaded spreadsheet: {exc}")
            return

        summary = aggregate_member_month(workbook, job.member_name, job.target_month)
        # hour_stats is committed here, before the LLM call, so a later provider failure
        # still leaves the deterministic numbers visible on the (failed) job row rather
        # than losing work that has already been computed.
        job.hour_stats = _summary_to_hour_stats(summary)
        await db.commit()

        job.status = JobStatus.EXTRACTING
        await db.commit()

        projects_context = await _gather_projects_context(db, job.user_id)
        completed_tasks_context = await _gather_completed_tasks_context(db, job.user_id, job.target_month)
        work_log_entries = _work_log_entries(summary)

        try:
            provider = await get_provider(db, job.user_id, job.provider, purpose="brag_document")
            user = await db.get(User, job.user_id)
            persona = user.agent_persona if user else AgentPersona.BUSINESS_ANALYST
            raw_result = await provider.generate_brag_document(
                BragDocumentInput(
                    member_name=job.member_name,
                    target_month=job.target_month,
                    work_log_entries=work_log_entries,
                    projects=projects_context,
                    completed_tasks=completed_tasks_context,
                ),
                json_schema=_BRAG_DOCUMENT_SCHEMA,
                persona=persona,
            )
        except ProviderError as exc:
            await _fail(db, job, exc.code, exc.message)
            return

        job.status = JobStatus.STRUCTURING
        await db.commit()

        result = normalize_brag_document(raw_result)

        job.result = result.model_dump(mode="json")
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        # Same reasoning as extraction_service/breakdown_service's catch-all: without
        # this, a bug here leaves the row stuck until the stale-job reaper, and Cancel
        # against an already-dead worker would have nothing left to stop.
        logger.exception("Unexpected error running brag document job %s", job_id)
        await db.rollback()
        await _fail(
            db, job, "UNEXPECTED_ERROR",
            "Something went wrong while drafting this document. Please try again.",
        )
