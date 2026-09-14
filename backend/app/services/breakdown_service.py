"""Orchestrates one AI work-breakdown job: ingest (optional) -> provider call -> normalize
-> persist; plus accepting/dismissing individual proposed tasks into real Task rows.

Mirrors extraction_service.py's shape (backend/DESIGN.md §1/§6: a plain async def(db, ...)
service, called by both the SAQ worker and directly in tests, with no FastAPI/queue
dependency) but with one additional, load-bearing function: normalize_breakdown(). See its
own docstring for why it must never raise.
"""

import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BREAKDOWN_ESTIMATE_SIZE_MINUTES
from app.ingest.extract import UnsupportedFormatError, ingest
from app.models.breakdown_job import BreakdownJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskSource, TaskStatus
from app.models.user import AgentPersona, User
from app.providers.base import BreakdownInput, ProviderError
from app.providers.registry import get_provider
from app.providers.schema_utils import inline_refs
from app.schemas.breakdown import (
    BreakdownAcceptItem,
    LLMBreakdownResult,
    LLMProposedTask,
)
from app.services import task_service

logger = logging.getLogger(__name__)

_BREAKDOWN_SCHEMA = inline_refs(LLMBreakdownResult.model_json_schema())

_VALID_PRIORITIES = {"low", "medium", "high", "urgent"}
_VALID_ESTIMATE_SIZES = {"xs", "s", "m", "l", "xl"}

_LEADING_NUMBERING_RE = re.compile(r"^\s*\d+(\.\d+)*[.)\s]+\s*")
# Control chars (excluding \t\n\r), zero-width spaces/joiners, and bidi override/isolate
# codepoints — a prompt-injection-adjacent hazard (docs/RESEARCH.md), e.g. a stray U+202E
# visually reverses everything after it, which is a cheap way to make a review row read
# differently than the plain text a user thinks they're accepting.
_UNSAFE_CHARS_RE = re.compile(
    '[\x00-\x08\x0b\x0c\x0e-\x1f'
    '\u200b-\u200f\u202a-\u202e\u2066-\u2069\ufeff]'
)

_MAX_TITLE_LEN = 200
_MAX_DESCRIPTION_LEN = 2000
_MAX_QUOTE_LEN = 160
_MAX_UNGROUNDED = 5


def _sanitize(text: str) -> str:
    return _UNSAFE_CHARS_RE.sub("", text)


def _truncate_at_word(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0]
    return (cut or text[:limit]).rstrip() + "…"


def _coerce_task(raw: object, index: int, notes: list[str]) -> dict | None:
    """Best-effort coercion of one provider-emitted task into a clean field dict, or None
    if it's unsalvageable (no title). Every branch below repairs rather than rejects —
    that's the whole point of this function existing separately from Pydantic validation,
    which would only ever reject."""
    if not isinstance(raw, dict):
        notes.append(f"Dropped one proposed task with an unexpected shape (item {index + 1}).")
        return None

    title = _sanitize(str(raw.get("title") or "")).strip()
    title = _LEADING_NUMBERING_RE.sub("", title).strip()
    if not title:
        notes.append(f"Dropped an unnamed task (item {index + 1}).")
        return None
    if len(title) > _MAX_TITLE_LEN:
        title = _truncate_at_word(title, _MAX_TITLE_LEN)
        notes.append(f'Shortened an overly long task title: "{title}"')

    description = _sanitize(str(raw.get("description") or "")).strip()
    if len(description) > _MAX_DESCRIPTION_LEN:
        description = _truncate_at_word(description, _MAX_DESCRIPTION_LEN)
        notes.append(f'Shortened an overly long description on "{title}"')

    ref = str(raw.get("ref") or "").strip() or f"t{index + 1}"

    priority = raw.get("priority")
    if priority not in _VALID_PRIORITIES:
        priority = "medium"

    estimate_size = raw.get("estimate_size")
    if estimate_size not in _VALID_ESTIMATE_SIZES:
        estimate_size = None

    grounded = bool(raw.get("grounded", False))
    source_quote = raw.get("source_quote")
    source_quote = _sanitize(str(source_quote)).strip() if isinstance(source_quote, str) else ""
    if source_quote:
        source_quote = source_quote[:_MAX_QUOTE_LEN]
    if grounded and not source_quote:
        grounded = False
        notes.append(f'Marked "{title}" as a suggestion rather than grounded — no supporting quote was given.')

    phase = raw.get("phase")
    phase = _sanitize(str(phase)).strip()[:100] or None if isinstance(phase, str) else None

    parent_ref = raw.get("parent_ref")
    parent_ref = str(parent_ref).strip() or None if parent_ref else None

    return {
        "ref": ref,
        "title": title,
        "description": description,
        "grounded": grounded,
        "phase": phase,
        "parent_ref": parent_ref,
        "priority": priority,
        "estimate_size": estimate_size,
        "source_quote": source_quote or None,
    }


def normalize_breakdown(raw: dict, *, max_tasks: int) -> LLMBreakdownResult:
    """Repairs a raw provider response into a valid LLMBreakdownResult. Total, not
    partial: every malformed input this function is known to be tested against (see
    tests/test_breakdown_normalize.py) — an unknown parent_ref, a parent cycle, a 3+ level
    chain, a duplicate ref, a self-parent, a blank title, an over-length title/description,
    an unknown enum value, more items than max_tasks, or a grounded=true item with no
    quote — is repaired in place with a confidence_note recorded, never raised. A job that
    fails because the model returned one bad parent_ref is a worse outcome for the user
    than a job that says "I fixed 2 things."
    """
    notes: list[str] = []

    raw_tasks = raw.get("tasks") if isinstance(raw, dict) else None
    if not isinstance(raw_tasks, list):
        raw_tasks = []

    coerced: list[dict] = []
    seen_refs: set[str] = set()
    for index, item in enumerate(raw_tasks):
        task = _coerce_task(item, index, notes)
        if task is None:
            continue
        if task["ref"] in seen_refs:
            original_ref = task["ref"]
            task["ref"] = f"{original_ref}-{index + 1}"
            notes.append(f'Renamed a duplicate task reference "{original_ref}" to avoid a collision.')
        seen_refs.add(task["ref"])
        coerced.append(task)

    def _fix_parents(tasks: list[dict]) -> None:
        # A ref counts as "top-level" purely by not having a parent_ref of its own. Any
        # task whose parent_ref doesn't point at a top-level ref — because it's unknown,
        # points at itself, or points at another child (a 3+ level chain, or either half
        # of a two-item cycle) — gets promoted to top-level instead. This one membership
        # test enforces the depth-1 cap without ever walking a parent chain.
        top_level_refs = {t["ref"] for t in tasks if not t["parent_ref"]}
        for task in tasks:
            pr = task["parent_ref"]
            if pr and (pr == task["ref"] or pr not in top_level_refs):
                task["parent_ref"] = None
                notes.append(f'Moved "{task["title"]}" to the top level (its parent reference didn\'t resolve).')

    _fix_parents(coerced)

    if len(coerced) > max_tasks:
        dropped = len(coerced) - max_tasks
        coerced = coerced[:max_tasks]
        notes.append(f"Dropped {dropped} task(s) over the {max_tasks}-task cap.")
        # Dropping tail items can orphan a surviving child whose parent just got cut.
        _fix_parents(coerced)

    # The prompt asks for at most 5 ungrounded "suggested addition" tasks, but this is
    # deliberately NOT enforced as a hard drop here: if a model under-uses grounded=true
    # (e.g. marks real, well-founded tasks ungrounded because it couldn't produce an exact
    # quote), a hard cap would silently gut a legitimate 25-task breakdown down to 5. The
    # review UI already renders ungrounded items in their own "Suggested additions"
    # section, so keeping the volume visually contained belongs there, not as silent data
    # loss here — this only ever leaves a note.
    ungrounded_count = sum(1 for t in coerced if not t["grounded"])
    if ungrounded_count > _MAX_UNGROUNDED:
        notes.append(
            f"{ungrounded_count} tasks are suggestions not directly stated in the document "
            f"(more than the usual {_MAX_UNGROUNDED}) — review these separately."
        )

    tasks: list[LLMProposedTask] = []
    for t in coerced:
        try:
            tasks.append(LLMProposedTask.model_validate(t))
        except Exception:
            logger.exception("Unexpected validation failure on an already-sanitized breakdown task")
            notes.append(f'Dropped "{t.get("title", "?")}" due to an unexpected internal error.')

    raw_notes = raw.get("confidence_notes") if isinstance(raw, dict) else None
    if isinstance(raw_notes, list):
        for n in raw_notes[:10]:
            if isinstance(n, str) and n.strip():
                notes.append(_sanitize(n.strip())[:300])

    return LLMBreakdownResult(tasks=tasks, confidence_notes=notes[:20])


async def _fail(db: AsyncSession, job: BreakdownJob, code: str, message: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_message = message
    job.finished_at = datetime.now(UTC)
    await db.commit()


async def run_breakdown_job(db: AsyncSession, job_id: UUID) -> None:
    job = await db.get(BreakdownJob, job_id)
    if job is None:
        logger.error("breakdown job %s not found", job_id)
        return

    document = None
    if job.document_id:
        document = await db.get(Document, job.document_id)
        if document is None:
            await _fail(db, job, "DOCUMENT_MISSING", "The uploaded document is missing")
            return

    job.status = JobStatus.PARSING
    job.started_at = datetime.now(UTC)
    await db.commit()

    try:
        parsed = None
        if document is not None:
            try:
                data = Path(document.storage_path).read_bytes()
                parsed = ingest(data, document.filename)
            except UnsupportedFormatError as exc:
                await _fail(db, job, exc.code, exc.message)
                return
            except OSError as exc:
                await _fail(db, job, "STORAGE_ERROR", f"Could not read the uploaded file: {exc}")
                return

            if parsed.is_scanned and not parsed.raw_bytes:
                await _fail(
                    db, job, "NO_TEXT_FOUND",
                    "This looks like a scanned document with no extractable text.",
                )
                return

            job.is_scanned = parsed.is_scanned
            await db.commit()
        elif not (job.prompt or "").strip():
            await _fail(db, job, "NO_INPUT", "Provide a document, a description, or both.")
            return

        job.status = JobStatus.EXTRACTING
        await db.commit()

        try:
            provider = await get_provider(db, job.user_id, job.provider, purpose="breakdown")
            user = await db.get(User, job.user_id)
            persona = user.agent_persona if user else AgentPersona.BUSINESS_ANALYST
            raw_result = await provider.propose_breakdown(
                BreakdownInput(
                    raw_bytes=parsed.raw_bytes if parsed and parsed.mime_type == "application/pdf" else None,
                    mime_type=parsed.mime_type if parsed else None,
                    extracted_text=parsed.extracted_text if parsed else None,
                    filename=document.filename if document else None,
                    prompt=job.prompt,
                ),
                json_schema=_BREAKDOWN_SCHEMA,
                persona=persona,
                max_tasks=job.max_tasks,
            )
        except ProviderError as exc:
            await _fail(db, job, exc.code, exc.message)
            return

        job.status = JobStatus.STRUCTURING
        await db.commit()

        result = normalize_breakdown(raw_result, max_tasks=job.max_tasks)

        job.result = result.model_dump(mode="json")
        job.status = JobStatus.SUCCEEDED
        job.finished_at = datetime.now(UTC)
        await db.commit()
    except Exception:
        # Same reasoning as extraction_service.run_extraction_job's catch-all: without
        # this, a bug here leaves the row stuck until the stale-job reaper, and Cancel
        # against an already-dead worker would have nothing left to stop.
        logger.exception("Unexpected error running breakdown job %s", job_id)
        await db.rollback()
        await _fail(
            db, job, "UNEXPECTED_ERROR",
            "Something went wrong while processing this document. Please try again.",
        )


def _resolved_estimate_minutes(item: BreakdownAcceptItem) -> int | None:
    if item.estimate_minutes is not None:
        return item.estimate_minutes
    return BREAKDOWN_ESTIMATE_SIZE_MINUTES.get(item.estimate_size) if item.estimate_size else None


async def accept_breakdown_items(
    db: AsyncSession,
    user_id: UUID,
    project: Project,
    job: BreakdownJob,
    items: list[BreakdownAcceptItem],
    *,
    dry_run: bool = False,
) -> tuple[list[Task], list[dict], list[str]]:
    """Creates a Task for each accepted proposal. Resolvable across multiple partial
    accepts: `job.accepted_refs` (ref -> created Task id) from any earlier call is
    consulted so a second batch's parent_ref can attach to a task created in the first
    one. A ref already in job.accepted_refs is skipped outright — the idempotency
    guarantee that keeps a double-submit (or a refresh mid-accept) from creating
    duplicates.

    Depth is still capped at 1 here, same as every other task-creating path: a
    parent_ref is only honored if the thing it points to is (a) a sibling in this same
    batch that itself has no parent_ref, or (b) an already-created task that isn't
    itself a subtask. Anything else — unknown, self, a same-batch chain, or a
    previously-created task that already has its own parent — is promoted to top-level
    with a note back to the caller, never silently dropped or rejected outright.
    """
    ref_map: dict[str, str] = dict(job.accepted_refs)
    skipped: list[dict] = []
    promoted_refs: list[str] = []

    to_process = [item for item in items if item.ref not in ref_map]
    for item in items:
        if item.ref in ref_map:
            skipped.append({"ref": item.ref, "reason": "already accepted"})

    # Refs in *this batch* that are themselves parentless — the only valid targets for
    # another same-batch item's parent_ref (a task with a parent can't itself be a
    # parent).
    same_batch_top_level = {item.ref for item in to_process if not item.parent_ref}

    layer0: list[BreakdownAcceptItem] = []
    layer1: list[BreakdownAcceptItem] = []
    for item in to_process:
        if not item.parent_ref:
            layer0.append(item)
            continue

        if item.parent_ref in ref_map:
            parent_task = await db.get(Task, UUID(ref_map[item.parent_ref]))
            if parent_task is not None and parent_task.parent_id is None:
                layer0.append(item)  # valid: an existing, still-top-level task
            else:
                promoted_refs.append(item.ref)
                layer0.append(item.model_copy(update={"parent_ref": None}))
            continue

        if item.parent_ref in same_batch_top_level:
            layer1.append(item)  # depends on a layer0 sibling created below
        else:
            promoted_refs.append(item.ref)
            layer0.append(item.model_copy(update={"parent_ref": None}))

    created: list[Task] = []

    async def _create_one(item: BreakdownAcceptItem, parent_task_id: UUID | None) -> Task:
        position = await task_service._next_position(db, project.id, TaskStatus.TODO, parent_task_id)
        task = Task(
            # dry_run never calls db.add()/flush() below, so nothing would normally
            # populate the Python-side id default or the server-side timestamp
            # defaults — filled in by hand here so the preview response still has real
            # values. This also sidesteps a much worse problem than a missing id: a
            # session-wide db.rollback() to undo a real INSERT expires *every* object
            # in the shared session (project, job, anything else already loaded), not
            # just the ones this function touched — poisoning the caller's session for
            # any synchronous attribute access after this call returns. Simply never
            # writing anything avoids that class of bug entirely, not just this
            # instance of it.
            id=uuid4() if dry_run else None,
            user_id=user_id,
            project_id=project.id,
            parent_id=parent_task_id,
            title=item.title,
            description=item.description,
            status=TaskStatus.TODO,
            priority=TaskPriority(item.priority),
            source=TaskSource.AI,
            estimate_minutes=_resolved_estimate_minutes(item),
            due_date=None,
            position=position,
        )
        if dry_run:
            now = datetime.now(UTC)
            task.created_at = now
            task.updated_at = now
        else:
            db.add(task)
            await db.flush()
        ref_map[item.ref] = str(task.id)
        return task

    for item in layer0:
        parent_task_id = UUID(ref_map[item.parent_ref]) if item.parent_ref else None
        created.append(await _create_one(item, parent_task_id))

    for item in layer1:
        # layer0 above has already created every same-batch top-level task, so this
        # lookup always hits.
        parent_task_id = UUID(ref_map[item.parent_ref])
        created.append(await _create_one(item, parent_task_id))

    if not dry_run:
        job.accepted_refs = ref_map
        await db.commit()
        for task in created:
            await db.refresh(task)

    return created, skipped, promoted_refs


async def dismiss_breakdown_refs(db: AsyncSession, job: BreakdownJob, refs: list[str]) -> BreakdownJob:
    existing = set(job.dismissed_refs)
    existing.update(refs)
    job.dismissed_refs = sorted(existing)[:200]
    await db.commit()
    await db.refresh(job)
    return job
