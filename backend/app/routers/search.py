import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.ai_provider_setting import ProviderName
from app.models.user import User
from app.providers.base import ProviderError
from app.schemas.search import SearchAnswer, SearchAskRequest, SearchResponse
from app.services import search_service

router = APIRouter(prefix="/search", tags=["search"])

# Fast SQL, no LLM — separate from /search/ask so the instant results never wait on a
# provider call (which needs a configured API key and takes 2-8s).


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(min_length=1, max_length=200),
    limit_per_group: int = Query(default=5, ge=1, le=50),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    return await search_service.search(db, user.id, q, limit_per_group=limit_per_group)


@router.post("/ask", response_model=SearchAnswer)
async def ask(
    payload: SearchAskRequest, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> SearchAnswer:
    provider_override = ProviderName(payload.provider) if payload.provider else None
    try:
        async with asyncio.timeout(20):
            return await search_service.answer_question(db, user, payload.q, provider_override=provider_override)
    except ProviderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"code": exc.code, "message": exc.message}) from exc
    except TimeoutError as exc:
        raise HTTPException(
            status.HTTP_504_GATEWAY_TIMEOUT,
            {"code": "SEARCH_ANSWER_TIMEOUT", "message": "That took too long to answer — try again."},
        ) from exc
