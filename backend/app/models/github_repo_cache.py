from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDPk


class GithubRepoCache(Base, UUIDPk):
    """Shared, cross-user cache of github_service.search_github_repos() results, keyed by
    a lowercased technology name. Overlapping technologies across many users' portfolios
    (e.g. "python", "react") should only ever cost one live GitHub call per TTL window —
    see app/services/github_cache_service.py."""

    __tablename__ = "github_repo_cache"

    technology: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    repos: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
