"""record_usage (services/usage_service.py) — best-effort LLM token-usage logging.
Writes a row on well-formed usage, no-ops silently on missing/falsy usage, and never
raises even given malformed input — a logging bug here must never break the real AI
call it's attached to.
"""

from sqlalchemy import select

from app.models.ai_provider_setting import ProviderName
from app.models.llm_usage_log import LLMUsageLog
from app.models.user import User
from app.services.usage_service import record_usage


async def _count_rows(db) -> int:
    return len((await db.execute(select(LLMUsageLog))).scalars().all())


async def test_record_usage_writes_a_row(db, user_a: User) -> None:
    await record_usage(
        db,
        user_id=user_a.id,
        provider=ProviderName.OPENAI,
        model="gpt-4o-mini",
        operation="chat",
        usage={"input_tokens": 120, "output_tokens": 45, "total_tokens": 165},
    )
    rows = (await db.execute(select(LLMUsageLog).where(LLMUsageLog.user_id == user_a.id))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.provider == ProviderName.OPENAI
    assert row.model == "gpt-4o-mini"
    assert row.operation == "chat"
    assert row.input_tokens == 120
    assert row.output_tokens == 45
    assert row.total_tokens == 165
    assert row.session_id is None


async def test_record_usage_noops_on_missing_usage(db, user_a: User) -> None:
    before = await _count_rows(db)
    await record_usage(
        db, user_id=user_a.id, provider=ProviderName.GEMINI, model="gemini-3.5-flash",
        operation="chat", usage=None,
    )
    await record_usage(
        db, user_id=user_a.id, provider=ProviderName.GEMINI, model="gemini-3.5-flash",
        operation="chat", usage={},
    )
    assert await _count_rows(db) == before


async def test_record_usage_never_raises_on_malformed_input(db, user_a: User) -> None:
    # "usage" here isn't a real UsageMetadata dict at all — record_usage must swallow
    # whatever this raises internally rather than propagate it to the caller.
    await record_usage(
        db,
        user_id=user_a.id,
        provider=ProviderName.OPENAI,
        model="gpt-4o-mini",
        operation="chat",
        usage="not-a-dict",  # type: ignore[arg-type]
    )
