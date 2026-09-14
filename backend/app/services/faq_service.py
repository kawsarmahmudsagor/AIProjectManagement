"""Orchestrates the "project fields -> curated FAQ" job: provider call -> normalize ->
persist. Runs automatically once per project, enqueued right after project creation
(routers/projects.py::create_project) — there is no user-facing trigger, status endpoint,
or cancel endpoint for this feature; it either quietly appears on the project detail page
or quietly doesn't (see normalize_faq's docstring on why a "repair, never reject"
normalizer matters even more here than elsewhere, since there is no review UI to surface a
partial failure to).

Mirrors thumbnail_service.py's shape (a single-shot structured-output call, no
image/fallback branching) rather than breakdown_service.py's multi-stage ingest pipeline —
there is no document to ingest, only the project's own already-saved fields.
"""

import logging
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.extraction_job import JobStatus
from app.models.faq_job import FAQJob
from app.models.project import Project
from app.models.user import AgentPersona, User
from app.providers.base import FAQPromptInput, ProviderError
from app.providers.registry import get_provider
from app.providers.schema_utils import inline_refs
from app.schemas.faq import MAX_FAQ_ITEMS, LLMFAQItem, LLMFAQResult

# Reused rather than redefined — same control-char/bidi-override hazard class this
# module's own _sanitize() needs to strip (see breakdown_service.py's own comment for
# the rationale: a stray bidi-override codepoint is a cheap way to make text read
# differently than what a plain-text render shows).
from app.services.breakdown_service import _UNSAFE_CHARS_RE

logger = logging.getLogger(__name__)

_FAQ_SCHEMA = inline_refs(LLMFAQResult.model_json_schema())

_MAX_QUESTION_LEN = 200
_MAX_ANSWER_LEN = 600

# Belt-and-suspenders alongside the prompt's own anti-genericity instruction
# (providers/prompts.py's _FAQ_GROUNDING_RULE) — the prompt is the primary defense, this
# is a cheap net for the obvious cases the model produces anyway. Drops silently: unlike
# normalize_breakdown's confidence_notes (rendered in a review UI), there is no reader for
# a note here, so there's nothing to gain by recording one.
_GENERIC_QUESTION_PATTERNS = [
    re.compile(r"what (technolog|tech stack|tools|programming language)", re.IGNORECASE),
    re.compile(r"what (was|is) (the |this )?project about", re.IGNORECASE),
    re.compile(r"how long did (it|the project) take", re.IGNORECASE),
    re.compile(r"what (was|is) (your|the) role", re.IGNORECASE),
]


def _sanitize(text: str) -> str:
    return _UNSAFE_CHARS_RE.sub("", text).strip()


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip() + "..."


def _is_generic(question: str) -> bool:
    return any(p.search(question) for p in _GENERIC_QUESTION_PATTERNS)


def build_prompt_input_from_project(project: Project) -> FAQPromptInput:
    return FAQPromptInput(
        name=project.name,
        role=project.role,
        technologies=project.technologies,
        description_text=project.description_long_text or project.description_short_text,
        responsibilities_text=project.responsibilities_long_text or project.responsibilities_short_text,
    )


def normalize_faq(raw: dict) -> LLMFAQResult:
    """Repairs a raw provider response the same way normalize_breakdown repairs a
    breakdown: never raises. Drops an item with an empty question or answer, strips
    unsafe control/bidi characters, truncates an overlong question/answer at a word
    boundary, drops an item matching _GENERIC_QUESTION_PATTERNS, dedupes
    case-insensitively-identical questions, and caps the result at MAX_FAQ_ITEMS. Fewer
    than MAX_FAQ_ITEMS (including zero) is a valid, expected outcome — see this module's
    docstring and providers/prompts.py's _FAQ_GROUNDING_RULE on why a thin project should
    yield fewer questions rather than generic filler."""
    items_raw = raw.get("items") if isinstance(raw, dict) else None
    if not isinstance(items_raw, list):
        return LLMFAQResult(items=[])

    seen: set[str] = set()
    items: list[LLMFAQItem] = []
    for entry in items_raw:
        if not isinstance(entry, dict):
            continue
        question = _sanitize(str(entry.get("question") or ""))
        answer = _sanitize(str(entry.get("answer") or ""))
        if not question or not answer:
            continue
        if _is_generic(question):
            continue
        question = _truncate_at_word(question, _MAX_QUESTION_LEN)
        answer = _truncate_at_word(answer, _MAX_ANSWER_LEN)
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(LLMFAQItem(question=question, answer=answer))
        if len(items) >= MAX_FAQ_ITEMS:
            break

    return LLMFAQResult(items=items)


async def _fail(db: AsyncSession, job: FAQJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def run_faq_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(FAQJob, job_id)
    if job is None:
        logger.error("FAQ job %s not found", job_id)
        return

    project = await db.get(Project, job.project_id)
    if project is None or project.user_id != job.user_id:
        await _fail(db, job, "PROJECT_MISSING", "That project no longer exists.")
        return

    job.status = JobStatus.PARSING  # assembling the prompt from the project's own fields
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        user = await db.get(User, job.user_id)
        persona = user.agent_persona if user else AgentPersona.BUSINESS_ANALYST
        ctx = build_prompt_input_from_project(project)

        job.status = JobStatus.EXTRACTING  # calling the model
        await db.commit()

        try:
            provider = await get_provider(db, job.user_id, job.provider, purpose="faq")
            raw = await provider.generate_faq(ctx, json_schema=_FAQ_SCHEMA, persona=persona)
        except ProviderError as exc:
            await _fail(db, job, exc.code, exc.message)
            return

        result = normalize_faq(raw)
        job.result = result.model_dump(mode="json")
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        # Same reasoning as breakdown_service.run_breakdown_job / thumbnail_service.
        # run_thumbnail_job's catch-all: without this, a bug here leaves the row stuck
        # non-terminal until the stale reaper, and here specifically it also means the
        # FAQ section silently never appears — worth still going to FAILED for
        # reap_stale_jobs' sweep and log visibility, even with no user watching.
        logger.exception("Unexpected error running FAQ job %s", job_id)
        await db.rollback()
        await _fail(db, job, "UNEXPECTED_ERROR", "Something went wrong while generating the FAQ.")


async def get_latest_result(db: AsyncSession, project_id: UUID) -> LLMFAQResult | None:
    """Single-project read used by routers/projects.py::_to_out() — the most recent
    SUCCEEDED FAQJob for this project, if any. No batched "many projects at once" form
    (unlike project_media_service.media_by_project) because FAQ is only ever rendered on
    the single-project detail page, never in a list."""
    stmt = (
        select(FAQJob.result)
        .where(FAQJob.project_id == project_id, FAQJob.status == JobStatus.SUCCEEDED)
        .order_by(FAQJob.created_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    return LLMFAQResult.model_validate(row) if row else None
