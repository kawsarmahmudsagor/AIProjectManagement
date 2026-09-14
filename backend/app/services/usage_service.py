"""Best-effort LLM token-usage logging (see models/llm_usage_log.py). Every write here
is wrapped so a logging bug can never break the real AI call it's attached to — missing
or malformed usage data just means that one call goes unlogged, not a failed job/turn.
Never commits itself: the caller's `db.add()`-then-flush rides along with whichever
commit the caller was already going to do, so this never adds an extra round-trip or a
partial-commit risk of its own.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider_setting import ProviderName
from app.models.llm_usage_log import LLMUsageLog


async def record_usage(
    db: AsyncSession,
    *,
    user_id: UUID,
    provider: ProviderName,
    model: str,
    operation: str,
    usage: dict | None,
    session_id: UUID | None = None,
) -> None:
    if not usage:
        return
    try:
        db.add(
            LLMUsageLog(
                user_id=user_id,
                session_id=session_id,
                provider=provider,
                model=model,
                operation=operation,
                input_tokens=usage.get("input_tokens") or 0,
                output_tokens=usage.get("output_tokens") or 0,
                total_tokens=usage.get("total_tokens") or 0,
            )
        )
        await db.flush()
    except Exception:  # noqa: BLE001, S110 — usage logging must never break the real call
        pass
