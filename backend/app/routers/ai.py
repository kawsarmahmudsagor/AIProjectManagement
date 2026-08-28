from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.providers.base import ProviderError
from app.providers.registry import get_provider, resolve_default_provider
from app.schemas.ai_settings import RewriteRequest, RewriteResponse
from app.services.ai_service import rewrite_field

router = APIRouter(prefix="/ai", tags=["ai"])

_CHAR_LIMITS = {"generate-short": 390, "enhance-short": 390, "enhance-long": 10_000}


@router.post("/rewrite", response_model=RewriteResponse)
async def rewrite(
    payload: RewriteRequest, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> RewriteResponse:
    # Resolved ahead of get_provider() so it's known even if get_provider() itself raises
    # (e.g. PROVIDER_NOT_CONFIGURED) — the frontend's provider-specific error popup needs
    # this regardless of which step failed.
    resolved_provider = payload.provider or await resolve_default_provider(db, user.id)

    try:
        provider = await get_provider(db, user.id, payload.provider)
        html, text = await rewrite_field(
            provider,
            op=payload.op,
            target_html=payload.target_html,
            source_html=payload.source_html,
            char_limit=_CHAR_LIMITS.get(payload.op),
            context=payload.context.model_dump() if payload.context else None,
            instruction=payload.instruction,
            persona=user.agent_persona,
        )
    except ProviderError as exc:
        raise HTTPException(
            422, {"code": exc.code, "message": exc.message, "provider": resolved_provider.value}
        ) from exc

    return RewriteResponse(html=html, text=text)
