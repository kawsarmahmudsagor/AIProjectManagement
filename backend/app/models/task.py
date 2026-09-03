import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class TaskStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskSource(StrEnum):
    MANUAL = "manual"
    AI = "ai"


# Shared Enum instances, one per Postgres TYPE — mirrors provider_name_enum in
# ai_provider_setting.py so CREATE TYPE is emitted exactly once. Declaration order is
# load-bearing for both: Postgres enums sort by declaration order, so `ORDER BY status,
# position` returns a whole board pre-grouped, and `ORDER BY priority DESC` needs no CASE.
task_status_enum = Enum(TaskStatus, name="task_status")
task_priority_enum = Enum(TaskPriority, name="task_priority")
task_source_enum = Enum(TaskSource, name="task_source")


class Task(Base, UUIDPk, Timestamps):
    """A unit of work under a Project. Solo/single-user, user_id-scoped like every other
    table here — no assignee, no organization.

    description is plain Text, not the {html,text} RichText pair Project uses: that pair
    exists to feed the export renderers and the Tiptap dual editor, and tasks are neither
    exported nor rich-text-edited (see backend/DESIGN.md §2's user_profiles note, which
    makes the same call for the same reason).

    due_date is a plain Date, not timestamptz: there is no users.timezone column, so a
    timestamptz due date would silently be UTC-interpreted and wrong by hours for a real
    user. Project.start_date/end_date already made this same choice.

    status/priority/source are fixed Postgres enums, not per-project configurable lists —
    see the migration's docstring for why. depth is capped at 1 (a task with a parent_id
    cannot itself be a parent) and enforced in services/task_service.py, not here.

    position is a plain integer, rewritten as a whole ordered list on reorder (never a
    per-move increment) — see services/task_service.py:reorder_tasks. It is not part of
    TaskUpdate; it only changes via create, a status change, or an explicit reorder call.
    """

    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_project_status_position", "project_id", "status", "position"),
        Index("ix_tasks_user_due_date", "user_id", "due_date"),
        # Makes a cross-project parent attachment structurally unrepresentable at the DB
        # level (task_service._validate_parent still must check this in Python too, since
        # this constraint alone can't express "and it isn't itself a subtask").
        ForeignKeyConstraint(
            ["project_id", "user_id"],
            ["projects.id", "projects.user_id"],
            ondelete="CASCADE",
            name="fk_tasks_project_user",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    status: Mapped[TaskStatus] = mapped_column(task_status_enum, default=TaskStatus.TODO, nullable=False)
    priority: Mapped[TaskPriority] = mapped_column(
        task_priority_enum, default=TaskPriority.MEDIUM, nullable=False
    )
    source: Mapped[TaskSource] = mapped_column(task_source_enum, default=TaskSource.MANUAL, nullable=False)

    estimate_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="tasks")  # noqa: F821
    parent: Mapped["Task | None"] = relationship(back_populates="subtasks", remote_side="Task.id")
    subtasks: Mapped[list["Task"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", passive_deletes=True
    )
