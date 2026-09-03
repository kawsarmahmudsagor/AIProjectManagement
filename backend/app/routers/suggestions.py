from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.repo_suggestion import RepoSuggestion
from app.models.user import User
from app.schemas.suggestion import RepoOut, RepoSuggestionOut
from app.services import suggestion_service

router = APIRouter(prefix="/suggestions", tags=["suggestions"])


def _to_out(s: RepoSuggestion) -> RepoSuggestionOut:
    return RepoSuggestionOut(
        id=s.id,
        technology=s.technology_display,
        repo=RepoOut(**s.repo),
        computed_at=s.computed_at,
        dismissed=s.dismissed,
        source=s.source.value,
    )


@router.get("/github", response_model=list[RepoSuggestionOut])
async def list_github_suggestions(
    scope: Literal["recent", "all"] = Query("recent"),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[RepoSuggestionOut]:
    """`scope=recent` (default, the Dashboard card): active suggestions from within the
    last day or so. `scope=all` (the Conversations page's Suggestions section): the
    complete history, dismissed or not — see suggestion_service.list_suggestions."""
    suggestions = await suggestion_service.list_suggestions(db, user.id, scope=scope)
    return [_to_out(s) for s in suggestions]


@router.post("/github/{suggestion_id}/dismiss", response_model=RepoSuggestionOut)
async def dismiss_github_suggestion(
    suggestion_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> RepoSuggestionOut:
    suggestion = await suggestion_service.dismiss_suggestion(db, user.id, suggestion_id)
    if suggestion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suggestion not found")
    return _to_out(suggestion)
