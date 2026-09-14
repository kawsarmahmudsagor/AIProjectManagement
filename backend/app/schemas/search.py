from typing import Literal

from pydantic import BaseModel, Field


class SearchHit(BaseModel):
    """One result row, uniform across all four kinds so the frontend renders one
    component regardless of which group it came from.

    `id` is a plain str, not a UUID: a technology hit's identity is its normalized name
    and an app-feature hit's is its registry slug — neither is a UUID, and a discriminated
    union here would push type-narrowing onto the frontend for no real gain.

    `href` is the frontend route to navigate to. The backend already owns that mapping
    for app_feature rows (the registry stores the path), so owning it for every kind
    keeps the search UI a dumb renderer and keeps all route knowledge in one place.
    """

    kind: Literal["project", "technology", "task", "app_feature"]
    id: str
    title: str
    subtitle: str = ""
    snippet: str = ""
    href: str
    score: float
    meta: dict = Field(default_factory=dict)


class SearchGroup(BaseModel):
    kind: Literal["project", "technology", "task", "app_feature"]
    label: str
    items: list[SearchHit]
    # The true match count before `limit_per_group` truncated `items`, so the frontend
    # can offer "N more results" instead of silently hiding them.
    total: int


class SearchResponse(BaseModel):
    q: str
    groups: list[SearchGroup]
    total: int


class SearchAskRequest(BaseModel):
    q: str = Field(min_length=1, max_length=500)
    provider: str | None = None


class SearchAnswer(BaseModel):
    answer: str
    citations: list[SearchHit] = Field(default_factory=list)
