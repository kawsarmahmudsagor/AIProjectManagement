"""Plain async def(db, ...) service functions per backend/DESIGN.md §1 — thin routers call
one of these each; SAQ background jobs (the future AI work-breakdown job) call the same
functions, never a router.
"""

from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskSource, TaskStatus
from app.schemas.task import (
    TaskBulkItem,
    TaskCreate,
    TaskSort,
    TaskUpdate,
)


class TaskValidationError(Exception):
    """Raised for a request-shaped problem that isn't "not found" — an invalid parent
    reference, a reorder task_ids list that doesn't match the column it claims to
    reorder. Mapped to 422 by the app-wide handler in app/main.py, mirroring how
    ResourceNotFoundError maps to 404."""


async def _next_position(
    db: AsyncSession, project_id: UUID, status: TaskStatus, parent_id: UUID | None
) -> int:
    stmt = select(func.max(Task.position)).where(
        Task.project_id == project_id,
        Task.status == status,
        Task.parent_id.is_(None) if parent_id is None else Task.parent_id == parent_id,
    )
    max_position = (await db.execute(stmt)).scalar_one_or_none()
    return (max_position or 0) + 100


async def _validate_parent(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    parent_id: UUID | None,
    *,
    self_id: UUID | None = None,
) -> None:
    """Re-validates a client-supplied parent_id against the DB on every write — never
    trust that a value round-tripped correctly. Depth is capped at 1: a task that already
    has a parent cannot itself become a parent."""
    if parent_id is None:
        return
    if self_id is not None and parent_id == self_id:
        raise TaskValidationError("A task cannot be its own parent")

    stmt = select(Task).where(
        Task.id == parent_id, Task.user_id == user_id, Task.project_id == project_id
    )
    parent = (await db.execute(stmt)).scalar_one_or_none()
    if parent is None:
        raise TaskValidationError("Parent task not found in this project")
    if parent.parent_id is not None:
        raise TaskValidationError("A subtask cannot itself be a parent (depth is capped at 1)")


def _completed_at_for(status: TaskStatus) -> datetime | None:
    return datetime.now(UTC) if status == TaskStatus.DONE else None


async def create_task(
    db: AsyncSession,
    user_id: UUID,
    project: Project,
    payload: TaskCreate,
    *,
    source: TaskSource = TaskSource.MANUAL,
) -> Task:
    await _validate_parent(db, user_id, project.id, payload.parent_id)
    position = await _next_position(db, project.id, payload.status, payload.parent_id)

    task = Task(
        user_id=user_id,
        project_id=project.id,
        parent_id=payload.parent_id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        source=source,
        estimate_minutes=payload.estimate_minutes,
        due_date=payload.due_date,
        position=position,
        completed_at=_completed_at_for(payload.status),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def create_tasks_bulk(
    db: AsyncSession,
    user_id: UUID,
    project: Project,
    items: list[TaskBulkItem],
    *,
    source: TaskSource,
) -> list[Task]:
    """All-or-nothing: nothing is committed until every item (and every nested subtask)
    validates. A mid-loop TaskValidationError propagates uncommitted — get_db's session
    close() rolls back whatever was flushed, so a half-inserted breakdown never lands."""
    created: list[Task] = []

    for item in items:
        await _validate_parent(db, user_id, project.id, item.parent_id)
        position = await _next_position(db, project.id, item.status, item.parent_id)

        parent = Task(
            user_id=user_id,
            project_id=project.id,
            parent_id=item.parent_id,
            title=item.title,
            description=item.description,
            status=item.status,
            priority=item.priority,
            source=source,
            estimate_minutes=item.estimate_minutes,
            due_date=item.due_date,
            position=position,
            completed_at=_completed_at_for(item.status),
        )
        db.add(parent)
        # Flush now — subtasks below need parent.id, and Task.id is a Python-side
        # default(uuid4), not populated on the instance until flush.
        await db.flush()
        created.append(parent)

        for index, sub in enumerate(item.subtasks):
            child = Task(
                user_id=user_id,
                project_id=project.id,
                parent_id=parent.id,
                title=sub.title,
                description=sub.description,
                status=sub.status,
                priority=sub.priority,
                source=source,
                estimate_minutes=sub.estimate_minutes,
                due_date=sub.due_date,
                # A freshly created parent has no existing children, so array index is
                # already the correct position — no need to query _next_position here.
                position=index * 100,
                completed_at=_completed_at_for(sub.status),
            )
            db.add(child)
            created.append(child)

    await db.commit()
    for task in created:
        await db.refresh(task)
    return created


async def list_tasks(
    db: AsyncSession,
    user_id: UUID,
    *,
    project_id: UUID | None = None,
    q: str | None = None,
    statuses: list[TaskStatus] | None = None,
    priorities: list[TaskPriority] | None = None,
    due_before: date | None = None,
    due_after: date | None = None,
    include_subtasks: bool = False,
    sort: TaskSort = "board",
    order: str = "asc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Task], int]:
    # Every filter predicate is built once and applied to BOTH queries below — copying
    # each filter into a separately-built count_query (as project_service.list_projects
    # does) is exactly how a wrong `total` sneaks in once there are several filters.
    filters = [Task.user_id == user_id]
    if project_id is not None:
        filters.append(Task.project_id == project_id)
    if not include_subtasks:
        filters.append(Task.parent_id.is_(None))
    if q:
        pattern = f"%{q}%"
        filters.append(or_(Task.title.ilike(pattern), Task.description.ilike(pattern)))
    if statuses:
        filters.append(Task.status.in_(statuses))
    if priorities:
        filters.append(Task.priority.in_(priorities))
    if due_before is not None:
        filters.append(Task.due_date <= due_before)
    if due_after is not None:
        filters.append(Task.due_date >= due_after)

    count_query = select(func.count()).select_from(Task).where(*filters)
    total = (await db.execute(count_query)).scalar_one()

    order_fn = asc if order == "asc" else desc
    query = select(Task).where(*filters)
    if sort == "board":
        # One request, whole board pre-grouped: status column order is the enum's
        # declaration order (todo, in_progress, blocked, done) — no CASE needed.
        query = query.order_by(Task.status, Task.position, Task.created_at, Task.id)
    elif sort == "position":
        query = query.order_by(order_fn(Task.position), Task.created_at, Task.id)
    elif sort == "due_date":
        query = query.order_by(order_fn(Task.due_date), Task.created_at, Task.id)
    elif sort == "priority":
        query = query.order_by(order_fn(Task.priority), Task.created_at, Task.id)
    elif sort == "created_at":
        query = query.order_by(order_fn(Task.created_at), Task.id)
    else:  # updated_at
        query = query.order_by(order_fn(Task.updated_at), Task.id)

    query = query.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return list(items), total


async def update_task(db: AsyncSession, user_id: UUID, task: Task, payload: TaskUpdate) -> Task:
    data = payload.model_dump(exclude_unset=True)

    if "parent_id" in data:
        await _validate_parent(db, user_id, task.project_id, data["parent_id"], self_id=task.id)

    target_status = data.get("status", task.status)
    target_parent = data.get("parent_id", task.parent_id)
    status_changed = "status" in data and data["status"] != task.status
    parent_changed = "parent_id" in data and data["parent_id"] != task.parent_id

    # Computed BEFORE mutating task.status/parent_id below — querying _next_position
    # after the mutation risks autoflush making this row's own (already-updated, but
    # still-old-position) attributes visible to the MAX() query in its new column.
    new_position = None
    if status_changed or parent_changed:
        new_position = await _next_position(db, task.project_id, target_status, target_parent)

    for field in ("title", "description", "status", "priority", "estimate_minutes", "due_date", "parent_id"):
        if field in data:
            setattr(task, field, data[field])

    if status_changed:
        task.completed_at = _completed_at_for(task.status)

    if new_position is not None:
        # A status or parent change re-appends at the end of the target column —
        # otherwise the task keeps its stale index from the column it just left, which
        # is the most common kanban backend bug.
        task.position = new_position

    await db.commit()
    await db.refresh(task)
    return task


async def delete_task(db: AsyncSession, task: Task) -> None:
    await db.delete(task)
    await db.commit()


async def reorder_tasks(
    db: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    status: TaskStatus,
    parent_id: UUID | None,
    task_ids: list[UUID],
) -> list[Task]:
    """Takes the complete ordered id list for one (status, parent_id) column and rewrites
    every position from array index — never a single "move to index N" delta. Scoped by
    user_id/project_id/status in the same query that fetches the rows, and asserts every
    requested id was actually matched: an UPDATE keyed on nothing but client-supplied ids
    would otherwise be a mass-assignment IDOR letting one user rewrite another's board."""
    stmt = select(Task).where(
        Task.id.in_(task_ids),
        Task.user_id == user_id,
        Task.project_id == project_id,
        Task.status == status,
        Task.parent_id.is_(None) if parent_id is None else Task.parent_id == parent_id,
    )
    rows = (await db.execute(stmt)).scalars().all()
    by_id = {t.id: t for t in rows}

    if len(by_id) != len(set(task_ids)):
        raise TaskValidationError(
            "One or more task ids are not in this column, or don't belong to this project"
        )

    for index, task_id in enumerate(task_ids):
        by_id[task_id].position = index * 100

    await db.commit()
    ordered = [by_id[task_id] for task_id in task_ids]
    for task in ordered:
        await db.refresh(task)
    return ordered


async def subtask_counts(db: AsyncSession, user_id: UUID, parent_ids: list[UUID]) -> dict[UUID, tuple[int, int]]:
    """One GROUP BY over the whole page of parent ids — looping per-row is an N+1 on
    every board load. Scoped by user_id too: an unscoped aggregate is the kind of leak
    that never shows up in a test that only checks a status code, because it returns a
    number rather than a row."""
    if not parent_ids:
        return {}

    stmt = (
        select(
            Task.parent_id,
            func.count().label("total"),
            func.count().filter(Task.status == TaskStatus.DONE).label("done"),
        )
        .where(Task.user_id == user_id, Task.parent_id.in_(parent_ids))
        .group_by(Task.parent_id)
    )
    rows = (await db.execute(stmt)).all()
    return {row.parent_id: (row.total, row.done) for row in rows}
