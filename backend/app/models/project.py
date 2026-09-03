import uuid
from datetime import date

from sqlalchemy import ARRAY, Boolean, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class Project(Base, UUIDPk, Timestamps):
    """Rich-text fields are stored as {field}_html/{field}_text pairs mirroring the
    frontend's RichText = {html, text} type (see backend/DESIGN.md §2). {field}_text is
    always recomputed server-side from {field}_html on write — the client pair is a UX
    convenience, not a trust boundary.
    """

    __tablename__ = "projects"
    __table_args__ = (
        # id alone is already the PK and already unique — this composite constraint
        # exists so tasks.(project_id, user_id) can carry a composite FK into
        # projects(id, user_id) (see models/task.py), making a cross-tenant task-parent
        # attachment structurally unrepresentable at the DB level. Must stay in sync with
        # the migration that creates it (uq_projects_id_user_id) — Base.metadata.create_all
        # (used by the test suite) only sees constraints declared here, not ones only
        # ever issued as raw Alembic DDL.
        UniqueConstraint("id", "user_id", name="uq_projects_id_user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(120), nullable=False)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    description_long_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_long_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_short_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description_short_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    responsibilities_long_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    responsibilities_long_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    responsibilities_short_html: Mapped[str] = mapped_column(Text, default="", nullable=False)
    responsibilities_short_text: Mapped[str] = mapped_column(Text, default="", nullable=False)

    technologies: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list, nullable=False)
    project_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    user: Mapped["User"] = relationship(back_populates="projects")  # noqa: F821
    documents: Mapped[list["Document"]] = relationship(back_populates="project")  # noqa: F821
    # passive_deletes=True is required, not cosmetic: without it, delete_project's
    # `await db.delete(project)` would SELECT every task and DELETE them one-by-one in
    # Python instead of letting Postgres's ON DELETE CASCADE (on tasks.project_id, via
    # the composite FK in models/task.py) do it in one statement.
    tasks: Mapped[list["Task"]] = relationship(  # noqa: F821
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )
