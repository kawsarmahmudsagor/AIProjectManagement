"""Jarvis's tools. Built per chat-turn (`build_tools`), not as module-level singletons
like the rest of this codebase prefers to do things — this is required here because most
of these close over one request's `db`/`user_id`, which must never be LLM-visible
tool-call arguments (the model could otherwise be prompted into pointing a tool at another
user's data). For github_search this closure isn't about scoping a query to this user's
rows (GitHub itself is queried the same way regardless of caller) — it's so the tool can
check/record this user's suggestion history via app.services.suggestion_service, so it
never repeats a repo already suggested to them (here or on the Dashboard's proactive
suggestions card — see app.services.suggestion_service.recompute_user_suggestions).

Only github_search talks outside this user's own data — every other tool is a read-only
(or, for the breakdown/brag-document pair below, write-only-on-explicit-confirmation)
operation against this same user's rows, scoped by user_id at the SQL layer, not by prompt
instruction.

propose_task_breakdown/apply_task_breakdown and generate_brag_document call
breakdown_service.run_breakdown_job/brag_document_service.run_brag_document_job directly
rather than going through workers/settings.py's SAQ enqueue — both are plain
`async def(db, job_id)` functions explicitly designed to be called either by the SAQ
worker or directly (see each module's own docstring), and a chat tool call is exactly
that "directly" case: the turn is already an in-flight async request, so there is nothing
to gain from a queue round-trip, and every other tool here already awaits a slow network
call in place the same way.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from langchain_core.tools import BaseTool, tool
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingest.extract import XLSX_MIME_TYPE
from app.models.brag_document_job import BragDocumentJob
from app.models.breakdown_job import BreakdownJob
from app.models.document import Document
from app.models.extraction_job import JobStatus
from app.models.project import Project
from app.models.task import Task, TaskStatus
from app.models.user import User
from app.providers.registry import resolve_default_provider
from app.schemas.breakdown import BreakdownAcceptItem
from app.services import breakdown_service, brag_document_service
from app.services.brag_document_service import default_brag_document_name
from app.services.github_service import search_github_repos
from app.services.portfolio_service import compute_technology_frequency
from app.services.standup_excel_service import (
    MEMBER_MATCH_CONFIDENCE_THRESHOLD,
    best_member_match,
    parse_standup_workbook,
)
from app.services.suggestion_service import get_suggested_repo_full_names, record_chat_suggestions

TOOL_LABELS = {
    "project_search": "Searching your projects…",
    "portfolio_analysis": "Analyzing your portfolio…",
    "github_search": "Searching GitHub…",
    "task_search": "Checking your tasks…",
    "task_summary": "Checking your tasks…",
    "propose_task_breakdown": "Drafting a task breakdown…",
    "apply_task_breakdown": "Creating tasks…",
    "list_uploaded_spreadsheets": "Checking your uploaded files…",
    "generate_brag_document": "Generating your brag document…",
}


def build_tools(db: AsyncSession, user_id: UUID) -> list[BaseTool]:
    # response_format="content_and_artifact": each tool below returns (content, artifact)
    # — `content` is the JSON string the LLM reads, `artifact` is the same data as a raw
    # dict, attached to the resulting ToolMessage.artifact untouched by any string
    # round-trip. agents/chatbot_graph.py reads `.artifact` (falling back to parsing
    # `.content` if a given LangChain version doesn't preserve it) so the structured
    # shape below is exactly what's stored in ChatMessage.tool_result and rendered as
    # rich cards (e.g. GitHub repos) by the frontend, with no re-parsing.

    @tool(response_format="content_and_artifact")
    async def project_search(
        query: str | None = None, technologies: list[str] | None = None, limit: int = 10
    ) -> tuple[str, dict]:
        """Search the current user's own saved projects by free-text query and/or
        required technologies. Use this whenever the user asks anything about their own
        projects, work history, or which of their projects use a given technology.
        Returns up to `limit` matching projects (current/most recent first) with name,
        role, dates, technologies, and short description/responsibilities text. If both
        `query` and `technologies` are omitted, returns the user's most recent projects."""
        stmt = select(Project).where(Project.user_id == user_id)
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Project.name.ilike(pattern),
                    Project.role.ilike(pattern),
                    Project.description_long_text.ilike(pattern),
                    Project.responsibilities_long_text.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Project.is_current.desc(), Project.start_date.desc())
        projects = list((await db.execute(stmt)).scalars().all())

        if technologies:
            # Filtered in Python (not SQL) for simple case-insensitive matching against
            # the free-text `technologies` array — same reasoning as portfolio_analysis
            # below, and correct at this table's expected per-user scale.
            wanted = {t.lower() for t in technologies}
            projects = [p for p in projects if wanted & {t.lower() for t in p.technologies}]

        projects = projects[:limit]
        result = {
            "projects": [
                {
                    "id": str(p.id),
                    "name": p.name,
                    "role": p.role,
                    "start_date": p.start_date.isoformat(),
                    "end_date": p.end_date.isoformat() if p.end_date else None,
                    "is_current": p.is_current,
                    "technologies": p.technologies,
                    # _text variants only — never _html — the LLM never needs markup.
                    "description_short_text": p.description_short_text,
                    "responsibilities_short_text": p.responsibilities_short_text,
                }
                for p in projects
            ],
            "count": len(projects),
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def portfolio_analysis(
        focus: Literal["technology_frequency", "technology_pairs", "timeline", "roles"],
        technologies: list[str] | None = None,
    ) -> tuple[str, dict]:
        """Analyze patterns across ALL of the current user's saved projects. Use this for
        cross-project questions like "which technologies do I use most", "what are my
        strongest technical areas", "which projects use both X and Y", or "show me my
        project timeline" — never for a question about one named project (use
        project_search for that). `focus` selects the aggregate:
        - technology_frequency: how many projects use each technology, most-used first.
        - technology_pairs: which projects use ALL of the given `technologies` together
          (required for this focus).
        - timeline: every project in chronological order.
        - roles: how many projects the user held each role on.
        This tool only returns factual counts/lists — it never judges what counts as a
        "strongest" area itself; that interpretation is yours to make from the data."""
        if focus == "technology_frequency":
            result = await compute_technology_frequency(db, user_id)
            return json.dumps(result), result

        stmt = select(Project).where(Project.user_id == user_id)
        projects = list((await db.execute(stmt)).scalars().all())

        if focus == "technology_pairs":
            wanted = {t.lower() for t in (technologies or [])}
            matches = [p for p in projects if wanted <= {t.lower() for t in p.technologies}]
            result = {
                "projects": [
                    {"id": str(p.id), "name": p.name, "technologies": p.technologies} for p in matches
                ]
            }

        elif focus == "timeline":
            ordered = sorted(projects, key=lambda p: p.start_date)
            result = {
                "projects": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "start_date": p.start_date.isoformat(),
                        "end_date": p.end_date.isoformat() if p.end_date else None,
                        "is_current": p.is_current,
                    }
                    for p in ordered
                ]
            }

        else:  # focus == "roles"
            role_counts: dict[str, int] = {}
            for p in projects:
                role_counts[p.role] = role_counts.get(p.role, 0) + 1
            ranked_roles = sorted(role_counts.items(), key=lambda kv: kv[1], reverse=True)
            result = {"roles": [{"role": role, "project_count": count} for role, count in ranked_roles]}

        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def github_search(query: str, limit: int = 5) -> tuple[str, dict]:
        """Search GitHub for real, currently well-maintained open-source repositories
        matching `query` (a technology, framework, or topic — e.g. "RAG framework
        python"). Use this to ground any specific repo recommendation instead of
        recalling one from memory, since your training data may be stale on stars or
        maintenance status. Only returns repos above a minimum star count that have
        pushed a commit within roughly the last year and are not archived. Never repeats
        a repo already suggested to this user, in this conversation or a past one."""
        limit = min(max(limit, 1), 10)
        already_suggested = await get_suggested_repo_full_names(db, user_id)

        # Over-fetch so filtering out repos this user has already seen still leaves
        # `limit` results where possible, without a second API call.
        result = await search_github_repos(query, limit=min(limit + 5, 10))
        if result.get("error"):
            return json.dumps(result), result

        fresh_repos = [r for r in result["repos"] if r["full_name"] not in already_suggested][:limit]
        await record_chat_suggestions(db, user_id, query, fresh_repos)

        result = {"repos": fresh_repos, "query_used": result["query_used"]}
        return json.dumps(result), result

    async def _resolve_project_id(project_name: str | None) -> tuple[UUID | None, str | None]:
        """Best-effort name match, scoped to this user's own projects — mirrors
        project_search's own ILIKE matching rather than requiring an exact title. Returns
        (None, a note) rather than raising when nothing matches, so the calling tool can
        report that plainly instead of the turn failing outright."""
        if not project_name:
            return None, None
        stmt = select(Project.id).where(
            Project.user_id == user_id, Project.name.ilike(f"%{project_name}%")
        )
        project_id = (await db.execute(stmt)).scalars().first()
        if project_id is None:
            return None, f'No project matching "{project_name}" was found.'
        return project_id, None

    @tool(response_format="content_and_artifact")
    async def task_search(
        project_name: str | None = None,
        statuses: list[Literal["todo", "in_progress", "blocked", "done"]] | None = None,
        q: str | None = None,
        limit: int = 10,
    ) -> tuple[str, dict]:
        """Search the current user's own tasks — the work items under their projects, not
        the projects themselves (use project_search for that). Use this for anything
        about what's left to do, what's blocked, or work matching a keyword — e.g. "what's
        blocked on the billing project", "show me my urgent tasks", "what have I done on
        X". `project_name` narrows to one project by a partial, case-insensitive name
        match (omit to search across all projects). `statuses` filters by status
        (todo/in_progress/blocked/done); omit to include every status. `q` matches task
        title or description. Returns both top-level tasks and subtasks, most urgent
        (earliest due date, then highest priority) first."""
        limit = min(max(limit, 1), 50)
        project_id, note = await _resolve_project_id(project_name)
        if project_name and project_id is None:
            result = {"tasks": [], "count": 0, "note": note}
            return json.dumps(result), result

        stmt = select(Task).where(Task.user_id == user_id)
        if project_id is not None:
            stmt = stmt.where(Task.project_id == project_id)
        if statuses:
            stmt = stmt.where(Task.status.in_(statuses))
        if q:
            pattern = f"%{q}%"
            stmt = stmt.where(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))

        # NULLS LAST so undated tasks don't crowd out ones with a real deadline; priority
        # (enum declaration order low->urgent, see models/task.py) breaks remaining ties.
        stmt = stmt.order_by(Task.due_date.is_(None), Task.due_date, Task.priority.desc())
        stmt = stmt.limit(limit)
        tasks = list((await db.execute(stmt)).scalars().all())

        result = {
            "tasks": [
                {
                    "id": str(t.id),
                    "project_id": str(t.project_id),
                    "parent_id": str(t.parent_id) if t.parent_id else None,
                    "title": t.title,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "estimate_minutes": t.estimate_minutes,
                }
                for t in tasks
            ],
            "count": len(tasks),
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def task_summary(project_name: str | None = None) -> tuple[str, dict]:
        """Summarize the current user's tasks: counts by status and by priority, how many
        are overdue, and the single next-due task. Use this for "what's my workload look
        like", "what's overdue", or "what should I work on next" — use task_search instead
        when the user wants an actual list of matching tasks. `project_name` narrows to
        one project (partial, case-insensitive match); omit to summarize across every
        project."""
        project_id, note = await _resolve_project_id(project_name)
        if project_name and project_id is None:
            return json.dumps({"note": note}), {"note": note}

        base_filters = [Task.user_id == user_id]
        if project_id is not None:
            base_filters.append(Task.project_id == project_id)

        status_stmt = (
            select(Task.status, func.count()).where(*base_filters).group_by(Task.status)
        )
        status_counts = {row[0].value: row[1] for row in (await db.execute(status_stmt)).all()}

        priority_stmt = (
            select(Task.priority, func.count())
            .where(*base_filters, Task.status != TaskStatus.DONE)
            .group_by(Task.priority)
        )
        priority_counts = {row[0].value: row[1] for row in (await db.execute(priority_stmt)).all()}

        today = datetime.now(UTC).date()
        overdue_stmt = select(func.count()).select_from(Task).where(
            *base_filters, Task.status != TaskStatus.DONE, Task.due_date < today
        )
        overdue_count = (await db.execute(overdue_stmt)).scalar_one()

        next_due_stmt = (
            select(Task)
            .where(*base_filters, Task.status != TaskStatus.DONE, Task.due_date.is_not(None))
            .order_by(Task.due_date)
            .limit(1)
        )
        next_due = (await db.execute(next_due_stmt)).scalars().first()

        result = {
            "status_counts": status_counts,
            "priority_counts_excluding_done": priority_counts,
            "overdue_count": overdue_count,
            "next_due": (
                {
                    "id": str(next_due.id),
                    "title": next_due.title,
                    "due_date": next_due.due_date.isoformat() if next_due.due_date else None,
                }
                if next_due
                else None
            ),
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def propose_task_breakdown(
        project_name: str, description: str, max_tasks: int = 25
    ) -> tuple[str, dict]:
        """Draft a proposed task breakdown for one of the user's own projects from a
        free-text description of the work — use this when the user asks you to break
        work down into tasks, plan out a feature, or turn a description into a task list.
        `project_name` narrows to one project (partial, case-insensitive match) — ask the
        user which project if it's ambiguous or they didn't say. `description` is your own
        clear write-up of the work to break down, based on what the user told you in this
        conversation — including the text of any document they attached to a chat message
        (attachments are already part of this conversation's content by the time you see
        it). If the user instead wants the document permanently stored against the
        project with a resumable, cancellable job (rather than a one-off chat mention),
        tell them to use the AI work breakdown button on that project's task page
        instead. This only DRAFTS a proposal — nothing is
        created yet. Returns each proposed task (ref, title, description, priority,
        estimate_size, whether it's grounded in the description or your own suggestion)
        plus a job_id. Show the proposal to the user and ask which tasks they want kept
        before calling apply_task_breakdown — never call apply_task_breakdown without the
        user first confirming which items (or "all") to accept."""
        project_id, note = await _resolve_project_id(project_name)
        if project_id is None:
            result = {"note": note or f'No project matching "{project_name}" was found.'}
            return json.dumps(result), result

        max_tasks = min(max(max_tasks, 1), 60)
        provider = await resolve_default_provider(db, user_id)
        job = BreakdownJob(
            user_id=user_id,
            project_id=project_id,
            provider=provider,
            prompt=description,
            max_tasks=max_tasks,
        )
        db.add(job)
        await db.commit()

        await breakdown_service.run_breakdown_job(db, job.id)
        await db.refresh(job)

        if job.status != JobStatus.SUCCEEDED:
            result = {
                "status": job.status.value,
                "error_message": job.error_message or "The breakdown could not be completed.",
            }
            return json.dumps(result), result

        result = {
            "job_id": str(job.id),
            "status": "succeeded",
            "tasks": job.result.get("tasks", []) if job.result else [],
            "confidence_notes": job.result.get("confidence_notes", []) if job.result else [],
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def apply_task_breakdown(job_id: str, refs: list[str] | None = None) -> tuple[str, dict]:
        """Create real Task rows from a breakdown job's proposed tasks, after the user has
        told you which ones to keep — never call this before the user has explicitly
        confirmed. `job_id` is the id returned by propose_task_breakdown. `refs` is the
        list of task `ref` values the user wants created; omit (or pass null) only when
        the user said to accept everything. Returns the tasks actually created, any that
        were skipped (e.g. already created by an earlier call), and any that were promoted
        to top-level because their parent wasn't also selected."""
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            result = {"note": "That breakdown job id doesn't look valid."}
            return json.dumps(result), result

        job = await db.get(BreakdownJob, job_uuid)
        if job is None or job.user_id != user_id:
            result = {"note": "No breakdown job found with that id."}
            return json.dumps(result), result
        if job.status != JobStatus.SUCCEEDED or not job.result:
            result = {"note": f"This breakdown job isn't in a completed state (status: {job.status.value})."}
            return json.dumps(result), result

        project = await db.get(Project, job.project_id)
        if project is None:
            result = {"note": "The project this breakdown belongs to no longer exists."}
            return json.dumps(result), result

        wanted = set(refs) if refs else None
        proposed_tasks = job.result.get("tasks", [])
        items = [
            BreakdownAcceptItem(
                ref=t["ref"],
                title=t["title"],
                description=t.get("description") or "",
                priority=t.get("priority") or "medium",
                estimate_size=t.get("estimate_size"),
                phase=t.get("phase"),
                parent_ref=t.get("parent_ref"),
            )
            for t in proposed_tasks
            if wanted is None or t["ref"] in wanted
        ]
        if not items:
            result = {"note": "None of the given refs matched a proposed task on this job."}
            return json.dumps(result), result

        created, skipped, promoted_refs = await breakdown_service.accept_breakdown_items(
            db, user_id, project, job, items
        )
        result = {
            "created": [{"id": str(t.id), "title": t.title} for t in created],
            "skipped": skipped,
            "promoted_refs": promoted_refs,
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def list_uploaded_spreadsheets() -> tuple[str, dict]:
        """List the user's own already-uploaded standup Excel (.xlsx) workbooks — use this
        before generate_brag_document, to find the document_id of the spreadsheet to use
        (or to check whether one has been uploaded at all). If this comes back empty, tell
        the user they need to upload their team's weekly standup .xlsx workbook first, via
        the Brag Documents page, before you can generate a brag document."""
        stmt = (
            select(Document)
            .where(Document.user_id == user_id, Document.mime_type == XLSX_MIME_TYPE)
            .order_by(Document.uploaded_at.desc())
            .limit(10)
        )
        documents = list((await db.execute(stmt)).scalars().all())
        result = {
            "documents": [
                {"id": str(d.id), "filename": d.filename, "uploaded_at": d.uploaded_at.isoformat()}
                for d in documents
            ]
        }
        return json.dumps(result), result

    @tool(response_format="content_and_artifact")
    async def generate_brag_document(
        document_id: str, member_name: str | None = None, target_month: str | None = None
    ) -> tuple[str, dict]:
        """Generate a monthly brag document from an already-uploaded standup workbook —
        use this when the user asks for a brag document / performance report, once you
        have (or have found via list_uploaded_spreadsheets) the document_id of their
        uploaded .xlsx. `member_name` should match a name row in the sheet — omit it to
        let this auto-detect the user's own row; if that comes back with `needs_input:
        "member_name"`, ask the user to pick one of the returned `candidates`.
        `target_month` should be like "August 2026" — omit it to auto-pick when the sheet
        only covers one month; if this comes back with `needs_input: "target_month"`, ask
        the user to pick one of the returned `available_months`. Re-call this tool once
        you have the missing value(s) from the user. On success this returns the drafted
        document — technical contributions grouped by project/initiative (each with
        optional sub-themes and a short key-contribution summary), an overall-impact
        summary across disciplines, team support, and learning bullets — plus the exact
        hour/holiday/leave math (never invented by you — always show these numbers exactly
        as returned). When presenting this, keep the structure (project groups, their
        sub-themes if any, key contributions, overall impact) rather than flattening it
        into one big list. This is automatically saved under the returned `name` (e.g.
        "August 2026 Brag Document") and will show up in the saved-documents list on the
        Brag Documents page — no separate save step. Mention that the user can view the
        formatted document and download it as DOCX/PDF from that page (opening it with
        this job's id, which you should include)."""
        try:
            document_uuid = UUID(document_id)
        except ValueError:
            result = {"note": "That document id doesn't look valid."}
            return json.dumps(result), result

        document = await db.get(Document, document_uuid)
        if document is None or document.user_id != user_id:
            result = {"note": "No uploaded spreadsheet found with that document id."}
            return json.dumps(result), result
        if document.mime_type != XLSX_MIME_TYPE:
            result = {"note": "That document isn't a standup Excel (.xlsx) workbook."}
            return json.dumps(result), result

        try:
            data = Path(document.storage_path).read_bytes()
            workbook = parse_standup_workbook(data, document.filename)
        except Exception as exc:
            result = {"note": f"Could not parse that spreadsheet: {exc}"}
            return json.dumps(result), result

        resolved_member = member_name
        if resolved_member:
            exact = next(
                (m for m in workbook.team_members if m.lower() == resolved_member.lower()), None
            )
            if exact is not None:
                resolved_member = exact
            else:
                matched, confidence = best_member_match(workbook.team_members, resolved_member)
                if matched is None or confidence < MEMBER_MATCH_CONFIDENCE_THRESHOLD:
                    result = {
                        "needs_input": "member_name",
                        "candidates": workbook.team_members,
                        "note": f'No confident match for "{resolved_member}" in this sheet.',
                    }
                    return json.dumps(result), result
                resolved_member = matched
        else:
            user = await db.get(User, user_id)
            matched, confidence = best_member_match(workbook.team_members, user.full_name if user else "")
            if matched is None or confidence < MEMBER_MATCH_CONFIDENCE_THRESHOLD:
                result = {
                    "needs_input": "member_name",
                    "candidates": workbook.team_members,
                    "note": "Couldn't auto-detect which row in the sheet is the user's own.",
                }
                return json.dumps(result), result
            resolved_member = matched

        resolved_month = target_month
        if resolved_month:
            if resolved_month not in workbook.available_months:
                result = {
                    "needs_input": "target_month",
                    "available_months": workbook.available_months,
                    "note": f'"{resolved_month}" isn\'t covered by this sheet.',
                }
                return json.dumps(result), result
        else:
            if len(workbook.available_months) == 1:
                resolved_month = workbook.available_months[0]
            else:
                result = {
                    "needs_input": "target_month",
                    "available_months": workbook.available_months,
                    "note": "This sheet covers more than one month.",
                }
                return json.dumps(result), result

        provider = await resolve_default_provider(db, user_id)
        job = BragDocumentJob(
            user_id=user_id,
            document_id=document.id,
            provider=provider,
            name=default_brag_document_name(resolved_month),
            member_name=resolved_member,
            target_month=resolved_month,
        )
        db.add(job)
        await db.commit()

        await brag_document_service.run_brag_document_job(db, job.id)
        await db.refresh(job)

        if job.status != JobStatus.SUCCEEDED:
            result = {
                "status": job.status.value,
                "error_message": job.error_message or "The brag document could not be generated.",
            }
            return json.dumps(result), result

        result = {
            "job_id": str(job.id),
            "name": job.name,
            "status": "succeeded",
            "result": job.result,
            "hour_stats": job.hour_stats,
        }
        return json.dumps(result), result

    return [
        project_search,
        portfolio_analysis,
        github_search,
        task_search,
        task_summary,
        propose_task_breakdown,
        apply_task_breakdown,
        list_uploaded_spreadsheets,
        generate_brag_document,
    ]
