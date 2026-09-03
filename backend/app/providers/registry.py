from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decrypt_secret
from app.models.ai_provider_setting import AIProviderSetting, ProviderName
from app.providers.base import LLMProvider, ProviderError
from app.providers.gemini import GeminiProvider
from app.providers.openai import OpenAIProvider

_settings = get_settings()


async def resolve_default_provider(db: AsyncSession, user_id: UUID) -> ProviderName:
    """Which provider to use when a caller doesn't specify one explicitly — the row
    marked `is_default` in Settings, else Gemini. Used both by `get_provider` below and
    by `documents.py` when stamping a new ExtractionJob, so document upload and
    `/ai/rewrite` always agree on "the active provider" (backend/DESIGN.md §4)."""
    query = select(AIProviderSetting.provider).where(
        AIProviderSetting.user_id == user_id, AIProviderSetting.is_default.is_(True)
    )
    default_provider = (await db.execute(query)).scalar_one_or_none()
    return default_provider or ProviderName.GEMINI


async def get_provider(
    db: AsyncSession,
    user_id: UUID,
    provider: ProviderName | None = None,
    *,
    purpose: Literal["extract", "rewrite", "chat", "brag_document"] = "rewrite",
) -> LLMProvider:
    """Resolve a user's configured provider. Falls back to whichever provider is marked
    `is_default`, then to Gemini, if `provider` isn't given explicitly.

    `purpose` doesn't currently change provider construction for either Gemini or
    OpenAI — it exists as its own literal so a future purpose-specific nuance (e.g. a
    different default model for chat) doesn't require touching every call site."""
    query = select(AIProviderSetting).where(AIProviderSetting.user_id == user_id)
    rows = {row.provider: row for row in (await db.execute(query)).scalars().all()}

    if provider is None:
        default_row = next((r for r in rows.values() if r.is_default), None)
        provider = default_row.provider if default_row else ProviderName.GEMINI

    row = rows.get(provider)

    if provider == ProviderName.GEMINI:
        if row is None or not row.encrypted_api_key:
            raise ProviderError("PROVIDER_NOT_CONFIGURED", "Gemini API key is not set — add it in Settings.")
        return GeminiProvider(
            api_key=decrypt_secret(row.encrypted_api_key),
            model=row.default_model or _settings.gemini_default_model,
        )

    if provider == ProviderName.OPENAI:
        if row is None or not row.encrypted_api_key:
            raise ProviderError("PROVIDER_NOT_CONFIGURED", "OpenAI API key is not set — add it in Settings.")
        return OpenAIProvider(
            api_key=decrypt_secret(row.encrypted_api_key),
            model=row.default_model or _settings.openai_default_model,
        )

    raise ProviderError("PROVIDER_UNKNOWN", f"Unknown provider: {provider}")
