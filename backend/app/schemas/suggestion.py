from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RepoOut(BaseModel):
    name: str
    full_name: str
    url: str
    description: str
    stars: int
    language: str | None
    pushed_at: str | None


class RepoSuggestionOut(BaseModel):
    id: UUID
    technology: str
    repo: RepoOut
    computed_at: datetime
    dismissed: bool
    # "dashboard" (computed from the user's top technologies) or "chat" (surfaced by
    # Jarvis's github_search tool during a conversation) — see models/repo_suggestion.py.
    source: str
