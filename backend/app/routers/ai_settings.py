from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.ai_provider_setting import AIProviderSetting, ProviderName
from app.models.user import User
from app.providers.catalog import (
    GEMINI_DEFAULT_MODEL,
    GEMINI_MODELS,
    OLLAMA_DEFAULT_MODEL,
    OLLAMA_MODELS,
)
from app.providers.gemini import GeminiProvider
from app.providers.ollama import OllamaProvider
from app.schemas.ai_settings import (
    ConnectionTestResult,
    ProviderModelCatalog,
    ProviderSettingOut,
    ProviderSettingUpdate,
)

router = APIRouter(prefix="/ai-settings", tags=["ai-settings"])


@router.get("/models", response_model=dict[ProviderName, ProviderModelCatalog])
async def list_model_catalog(user: User = CurrentUser) -> dict[ProviderName, ProviderModelCatalog]:
    return {
        ProviderName.GEMINI: ProviderModelCatalog(models=GEMINI_MODELS, default=GEMINI_DEFAULT_MODEL),
        ProviderName.OLLAMA: ProviderModelCatalog(models=OLLAMA_MODELS, default=OLLAMA_DEFAULT_MODEL),
    }


def _to_out(row: AIProviderSetting) -> ProviderSettingOut:
    return ProviderSettingOut(
        id=row.id,
        provider=row.provider,
        api_key_masked=mask_secret(decrypt_secret(row.encrypted_api_key)) if row.encrypted_api_key else None,
        base_url=row.base_url,
        default_model=row.default_model,
        is_default=row.is_default,
    )


@router.get("", response_model=list[ProviderSettingOut])
async def list_settings(user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ProviderSettingOut]:
    rows = (
        await db.execute(select(AIProviderSetting).where(AIProviderSetting.user_id == user.id))
    ).scalars().all()
    return [_to_out(r) for r in rows]


@router.put("/{provider}", response_model=ProviderSettingOut)
async def upsert_setting(
    provider: ProviderName,
    payload: ProviderSettingUpdate,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ProviderSettingOut:
    row = (
        await db.execute(
            select(AIProviderSetting).where(
                AIProviderSetting.user_id == user.id, AIProviderSetting.provider == provider
            )
        )
    ).scalar_one_or_none()

    if row is None:
        row = AIProviderSetting(user_id=user.id, provider=provider)
        db.add(row)

    if payload.api_key is not None:
        row.encrypted_api_key = encrypt_secret(payload.api_key) if payload.api_key else None
    if payload.base_url is not None:
        row.base_url = payload.base_url
    if payload.default_model is not None:
        row.default_model = payload.default_model
    if payload.is_default is not None:
        row.is_default = payload.is_default
        if payload.is_default:
            # only one default provider per user
            others = (
                await db.execute(
                    select(AIProviderSetting).where(
                        AIProviderSetting.user_id == user.id, AIProviderSetting.provider != provider
                    )
                )
            ).scalars().all()
            for other in others:
                other.is_default = False

    await db.commit()
    await db.refresh(row)
    return _to_out(row)


@router.post("/{provider}/test", response_model=ConnectionTestResult)
async def test_connection(
    provider: ProviderName,
    payload: ProviderSettingUpdate | None = None,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ConnectionTestResult:
    """Tests either the saved config, or (if provided) an unsaved candidate value from
    the settings form — so the "Test connection" button works before Save is clicked."""
    row = (
        await db.execute(
            select(AIProviderSetting).where(
                AIProviderSetting.user_id == user.id, AIProviderSetting.provider == provider
            )
        )
    ).scalar_one_or_none()

    api_key = payload.api_key if payload and payload.api_key else (
        decrypt_secret(row.encrypted_api_key) if row and row.encrypted_api_key else None
    )
    base_url = payload.base_url if payload and payload.base_url else (row.base_url if row else None)
    model = payload.default_model if payload and payload.default_model else (row.default_model if row else None)

    if provider == ProviderName.GEMINI:
        if not api_key:
            return ConnectionTestResult(ok=False, detail="Enter an API key first")
        client = GeminiProvider(api_key=api_key, model=model or GEMINI_DEFAULT_MODEL)
    else:
        client = OllamaProvider(
            base_url=base_url or "http://localhost:11434", model=model or OLLAMA_DEFAULT_MODEL, api_key=api_key
        )

    status_result = await client.test_connection()
    return ConnectionTestResult(ok=status_result.ok, detail=status_result.detail, models=status_result.models)
