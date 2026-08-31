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
