from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.models.project import Project
from app.models.task import Task, TaskPriority, TaskStatus
from app.models.user import User
from app.schemas.task import (
    TaskBulkCreateRequest,
    TaskBulkCreateResponse,
    TaskCreate,
    TaskListResponse,
    TaskOut,
    TaskReorderRequest,
    TaskSort,
    TaskSummary,
    TaskUpdate,
)
from app.services import task_service

# Two routers, mirroring routers/export.py's second APIRouter(prefix="/projects"):
# `router` is project-scoped (collection routes — list/create/bulk/reorder all need the
# project's ownership checked once up front); `tasks_router` is flat by-id, deliberately
# NOT nested under /projects/{project_id}/tasks/{task_id} — a handler that only checks
# the *project* is owned and then loads the task by id, without also checking
# task.project_id == project_id, is a working IDOR that reviews right past you.
router = APIRouter(prefix="/projects", tags=["tasks"])
tasks_router = APIRouter(prefix="/tasks", tags=["tasks"])


def _to_out(task: Task, counts: dict[UUID, tuple[int, int]] | None = None) -> TaskOut:
    total, done = (counts or {}).get(task.id, (0, 0))
    return TaskOut(
        id=task.id,
        project_id=task.project_id,
        parent_id=task.parent_id,
        title=task.title,
        description=task.description,
        status=task.status,
        priority=task.priority,
        source=task.source,
        estimate_minutes=task.estimate_minutes,
        due_date=task.due_date,
        position=task.position,
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at,
        subtask_total=total,
        subtask_done=done,
    )


def _to_summary(task: Task, counts: dict[UUID, tuple[int, int]] | None = None) -> TaskSummary:
    total, done = (counts or {}).get(task.id, (0, 0))
    return TaskSummary(
        id=task.id,
        project_id=task.project_id,
        parent_id=task.parent_id,
        title=task.title,
        status=task.status,
        priority=task.priority,
        source=task.source,
        estimate_minutes=task.estimate_minutes,
        due_date=task.due_date,
        position=task.position,
        completed_at=task.completed_at,
        subtask_total=total,
        subtask_done=done,
    )


async def _get_owned_project(project_id: UUID, user: User, db: AsyncSession) -> Project:
    return await require_owned(db, Project, project_id, user.id, resource="Project")


@router.get("/{project_id}/tasks", response_model=TaskListResponse)
async def list_project_tasks(
    project_id: UUID,
    q: str | None = Query(default=None),
    status_: list[TaskStatus] | None = Query(default=None, alias="status"),
    priority: list[TaskPriority] | None = Query(default=None),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    include_subtasks: bool = Query(default=False),
    sort: TaskSort = Query(default="board"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    project = await _get_owned_project(project_id, user, db)
    # sort="board" (the default) with page_size=100 returns the whole board pre-grouped
    # by status in one request — no per-column fetch needed.
    items, total = await task_service.list_tasks(
        db,
        user.id,
        project_id=project.id,
        q=q,
        statuses=status_,
        priorities=priority,
        due_before=due_before,
        due_after=due_after,
        include_subtasks=include_subtasks,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    counts = await task_service.subtask_counts(db, user.id, [t.id for t in items])
    return TaskListResponse(items=[_to_summary(t, counts) for t in items], total=total)


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def create_project_task(
    project_id: UUID, payload: TaskCreate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> TaskOut:
    project = await _get_owned_project(project_id, user, db)
    task = await task_service.create_task(db, user.id, project, payload)
    return _to_out(task)


@router.post(
    "/{project_id}/tasks/bulk", response_model=TaskBulkCreateResponse, status_code=status.HTTP_201_CREATED
)
async def create_project_tasks_bulk(
    project_id: UUID,
    payload: TaskBulkCreateRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TaskBulkCreateResponse:
    project = await _get_owned_project(project_id, user, db)
    tasks = await task_service.create_tasks_bulk(db, user.id, project, payload.tasks, source=payload.source)
    return TaskBulkCreateResponse(items=[_to_out(t) for t in tasks], created=len(tasks))


@router.post("/{project_id}/tasks/reorder", response_model=TaskListResponse)
async def reorder_project_tasks(
    project_id: UUID,
    payload: TaskReorderRequest,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    await _get_owned_project(project_id, user, db)
    tasks = await task_service.reorder_tasks(
        db, user.id, project_id, payload.status, payload.parent_id, payload.task_ids
    )
    counts = await task_service.subtask_counts(db, user.id, [t.id for t in tasks])
    return TaskListResponse(items=[_to_summary(t, counts) for t in tasks], total=len(tasks))


@tasks_router.get("", response_model=TaskListResponse)
async def list_tasks(
    project_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    status_: list[TaskStatus] | None = Query(default=None, alias="status"),
    priority: list[TaskPriority] | None = Query(default=None),
    due_before: date | None = Query(default=None),
    due_after: date | None = Query(default=None),
    include_subtasks: bool = Query(default=False),
    sort: TaskSort = Query(default="board"),
    order: Literal["asc", "desc"] = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    items, total = await task_service.list_tasks(
        db,
        user.id,
        project_id=project_id,
        q=q,
        statuses=status_,
        priorities=priority,
        due_before=due_before,
        due_after=due_after,
        include_subtasks=include_subtasks,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    counts = await task_service.subtask_counts(db, user.id, [t.id for t in items])
    return TaskListResponse(items=[_to_summary(t, counts) for t in items], total=total)


@tasks_router.get("/{task_id}", response_model=TaskOut)
async def get_task(task_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> TaskOut:
    task = await require_owned(db, Task, task_id, user.id, resource="Task")
    counts = await task_service.subtask_counts(db, user.id, [task.id])
    return _to_out(task, counts)


@tasks_router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID, payload: TaskUpdate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> TaskOut:
    task = await require_owned(db, Task, task_id, user.id, resource="Task")
    task = await task_service.update_task(db, user.id, task, payload)
    counts = await task_service.subtask_counts(db, user.id, [task.id])
    return _to_out(task, counts)


@tasks_router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> None:
    task = await require_owned(db, Task, task_id, user.id, resource="Task")
    await task_service.delete_task(db, task)
