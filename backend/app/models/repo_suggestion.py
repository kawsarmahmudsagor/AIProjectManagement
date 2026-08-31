import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPk


class SuggestionSource(StrEnum):
    DASHBOARD = "dashboard"
    CHAT = "chat"


suggestion_source_enum = Enum(SuggestionSource, name="suggestion_source")


class RepoSuggestion(Base, UUIDPk):
    """One row per (user, technology, repo) ever suggested to that user — the dashboard's
    "Suggested for you" card reads the non-dismissed rows, and the same table is the
    no-repeat log both the dashboard recompute and the in-chat github_search tool check
    against before offering a repo again (app/services/suggestion_service.py,
    app/agents/chat_tools.py). The no-repeat check itself queries by (user_id,
    repo_full_name) alone, ignoring technology/source, so a repo already suggested under
    one technology (or via chat) is never re-suggested under a different one either."""

    __tablename__ = "repo_suggestions"
    __table_args__ = (
        UniqueConstraint("user_id", "technology", "repo_full_name", name="uq_repo_suggestions_user_tech_repo"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    technology: Mapped[str] = mapped_column(String(40), nullable=False)
    technology_display: Mapped[str] = mapped_column(String(40), nullable=False)
    repo_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo: Mapped[dict] = mapped_column(JSON, nullable=False)
    source: Mapped[SuggestionSource] = mapped_column(
        suggestion_source_enum, default=SuggestionSource.DASHBOARD, nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
