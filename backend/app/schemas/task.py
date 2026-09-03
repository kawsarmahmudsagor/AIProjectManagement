from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task import TaskPriority, TaskSource, TaskStatus

TaskSort = Literal["board", "position", "due_date", "priority", "created_at", "updated_at"]
SortOrder = Literal["asc", "desc"]


class TaskBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    estimate_minutes: int | None = Field(default=None, ge=1, le=100_000)
    due_date: date | None = None
    parent_id: UUID | None = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    """All fields optional — PATCH semantics (payload.model_dump(exclude_unset=True), same
    as ProjectUpdate). Deliberately excludes project_id, user_id, source, position, and
    completed_at — those are never client-writable via this schema. position changes only
    via create, a status transition, or POST .../reorder; completed_at is derived from a
    status transition in the service; source is set once at insert time in the envelope of
    TaskCreate/TaskBulkCreateRequest, never here."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    estimate_minutes: int | None = Field(default=None, ge=1, le=100_000)
    due_date: date | None = None
    parent_id: UUID | None = None


class TaskOut(TaskBase):
    id: UUID
    project_id: UUID
    source: TaskSource
    position: int
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    subtask_total: int = 0
    subtask_done: int = 0

    model_config = {"from_attributes": True}


class TaskSummary(BaseModel):
    """List-row projection — same fields as TaskOut but without description, matching
    ProjectSummary's "no long text in list views" convention."""

    id: UUID
    project_id: UUID
    parent_id: UUID | None
    title: str
    status: TaskStatus
    priority: TaskPriority
    source: TaskSource
    estimate_minutes: int | None
    due_date: date | None
    position: int
    completed_at: datetime | None
    subtask_total: int = 0
    subtask_done: int = 0

    model_config = {"from_attributes": True}


class TaskListResponse(BaseModel):
    items: list[TaskSummary]
    total: int


class TaskReorderRequest(BaseModel):
    """The complete ordered id list for one (status, parent_id) column — never a single
    "move this item to index N" delta. See services/task_service.py:reorder_tasks."""

    status: TaskStatus
    parent_id: UUID | None = None
    task_ids: list[UUID] = Field(min_length=1, max_length=500)


class TaskSubtaskCreate(BaseModel):
    """A subtask nested inside one TaskBulkItem. No parent_id field — unlike a top-level
    TaskBulkItem (which may attach to an *existing* task via the inherited parent_id),
    a nested subtask's parent is always the enclosing item, assigned by the service
    after that item's row is flushed. This is what keeps the depth cap at 1 structurally
    true of the request shape, not just enforced after the fact.

    extra="forbid" is deliberate: without it, a client attempting 3-level nesting (a
    "subtasks" key inside one of these) would have that key silently dropped by
    Pydantic's default extra="ignore" — quietly truncating the request instead of
    rejecting it. Forbidding extra fields turns that into a clean 422 at the request
    boundary, before the service ever runs.
    """

    model_config = {"extra": "forbid"}

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    estimate_minutes: int | None = Field(default=None, ge=1, le=100_000)
    due_date: date | None = None


class TaskBulkItem(TaskBase):
    """parent_id (inherited from TaskBase) may point at an existing task — "add these to
    task X" — validated exactly like a single create. subtasks are brand-new rows created
    in the same request, one level only."""

    subtasks: list[TaskSubtaskCreate] = Field(default_factory=list, max_length=50)


class TaskBulkCreateRequest(BaseModel):
    """source sits on the envelope, not per-item, and is absent from TaskUpdate — so
    provenance is set once at insert and can never be flipped afterward. It is advisory
    display metadata at the same trust level as `title`; nothing authorizes on it."""

    source: TaskSource = TaskSource.MANUAL
    tasks: list[TaskBulkItem] = Field(min_length=1, max_length=100)


class TaskBulkCreateResponse(BaseModel):
    items: list[TaskOut]
    created: int
