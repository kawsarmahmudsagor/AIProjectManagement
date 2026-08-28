import uuid
from datetime import date

from sqlalchemy import ARRAY, Boolean, Date, ForeignKey, String, Text
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
