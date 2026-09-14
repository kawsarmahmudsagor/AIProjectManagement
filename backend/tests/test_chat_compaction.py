"""should_compact (chat_service.py) — the token-based replacement for the old flat
message-count compaction trigger. Uses the real tiktoken encoder (no mocking): a small
history stays under budget, a large one crosses it once the estimate is sized against a
small-context model, and a failure in the estimate/model-lookup path falls back to the
old message-count check rather than silently never compacting.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider_setting import AIProviderSetting, ProviderName
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.user import ChatProvider, User
from app.services import chat_service


async def _make_session(db: AsyncSession, user: User) -> ChatSession:
    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def _add_messages(db: AsyncSession, session: ChatSession, count: int, content: str) -> None:
    for _ in range(count):
        db.add(ChatMessage(session_id=session.id, role=ChatRole.USER, content=content))
    await db.commit()


@pytest_asyncio.fixture
async def openai_small_model(db: AsyncSession, user_a: User) -> None:
    """Pins user_a to a real, small-context OpenAI model (gpt-4o-mini, 128K per
    catalog.MODEL_CONTEXT_WINDOWS) so a synthetic large history can realistically cross
    the compaction budget (50% of 128K = 64K tokens) without needing an enormous
    fixture."""
    user_a.chat_provider = ChatProvider.OPENAI
    db.add(
        AIProviderSetting(
            user_id=user_a.id,
            provider=ProviderName.OPENAI,
            encrypted_api_key="unused-in-this-test",
            default_model="gpt-4o-mini",
            is_default=True,
        )
    )
    await db.commit()


async def test_should_compact_false_for_small_history(db: AsyncSession, user_a: User) -> None:
    session = await _make_session(db, user_a)
    await _add_messages(db, session, count=15, content="hello there, how are you today?")
    assert await chat_service.should_compact(db, user_a, session.id) is False


async def test_should_compact_false_when_at_or_under_keep_recent(db: AsyncSession, user_a: User) -> None:
    session = await _make_session(db, user_a)
    await _add_messages(db, session, count=chat_service._COMPACTION_KEEP_RECENT, content="x" * 10_000)
    assert await chat_service.should_compact(db, user_a, session.id) is False


async def test_should_compact_true_once_over_token_budget(
    db: AsyncSession, user_a: User, openai_small_model: None
) -> None:
    session = await _make_session(db, user_a)
    # ~2000 words/message * 20 messages is comfortably more than 64K tokens (50% of
    # gpt-4o-mini's 128K window) — well past the budget, not a borderline case.
    long_message = "the quick brown fox jumps over the lazy dog " * 2000
    await _add_messages(db, session, count=20, content=long_message)
    assert await chat_service.should_compact(db, user_a, session.id) is True


async def test_should_compact_falls_back_to_message_count_on_error(
    db: AsyncSession, user_a: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = await _make_session(db, user_a)
    over_fallback = chat_service.COMPACTION_THRESHOLD + 1
    await _add_messages(db, session, count=over_fallback, content="short")

    def _raise(*args, **kwargs):
        raise RuntimeError("simulated tokenizer failure")

    monkeypatch.setattr(chat_service, "estimate_tokens", _raise)
    assert await chat_service.should_compact(db, user_a, session.id) is True

    # Same broken estimator, but now under the message-count fallback too.
    session2 = await _make_session(db, user_a)
    await _add_messages(db, session2, count=chat_service._COMPACTION_KEEP_RECENT + 1, content="short")
    assert await chat_service.should_compact(db, user_a, session2.id) is False
