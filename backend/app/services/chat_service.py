"""Orchestrates Jarvis's chat turns: session lifecycle, provider/tool/prompt resolution,
history replay, and persisting the new messages agents/chatbot_graph.stream_chat produces.
Mirrors ai_service.py's shape — plain async defs, db: AsyncSession, resolve the provider
via get_provider(), catch ProviderError explicitly plus a catch-all fallback so a chat
turn never hangs the SSE stream half-open.
"""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.chat_tools import TOOL_LABELS, build_tools
from app.agents.chatbot_graph import stream_chat
from app.models.ai_provider_setting import ProviderName
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.user import ChatProvider, User
from app.providers.base import ProviderError
from app.providers.prompts import build_chatbot_system_prompt
from app.providers.registry import get_provider
from app.schemas.chat import ChatSSEEvent
from app.services.profile_service import build_context_digest


class ChatSessionNotFoundError(Exception):
    pass


async def get_or_create_current_session(db: AsyncSession, user: User) -> ChatSession:
    """Returns the user's most recent session, or creates one. v1's frontend only ever
    operates on this single "current" session — no session-switcher UI yet — though the
    schema supports multiple sessions per user for that to be a later, non-breaking
    addition (see the plan's Part A.2)."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.last_message_at.desc())
        .limit(1)
    )
    session = (await db.execute(stmt)).scalars().first()
    if session is not None:
        return session

    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.flush()

    # Deterministic template greeting, never an LLM call — this is the one message every
    # single user always sees, so it can't misfire, hallucinate, or cost a token. Uses
    # only the user's chat display name (preferred name, else first name) — never the
    # full name, designation, team, or any Profile field.
    greeting = ChatMessage(
        session_id=session.id,
        role=ChatRole.ASSISTANT,
        content=(
            f"Hi {user.chat_display_name}! I'm Jarvis, your Project Intelligence & "
            "Technology Advisor. Ask me about your projects, cross-project tech "
            "patterns, or open-source recommendations — I'll always ground anything "
            "about your own work in your real project data."
        ),
    )
    db.add(greeting)
    await db.commit()
    await db.refresh(session)
    return session


async def list_sessions(db: AsyncSession, user_id: UUID) -> list[ChatSession]:
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.last_message_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def delete_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> None:
    session = await _get_owned_session(db, user_id, session_id)
    await db.delete(session)
    await db.commit()


async def _get_owned_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> ChatSession:
    session = await db.get(ChatSession, session_id)
    if session is None or session.user_id != user_id:
        raise ChatSessionNotFoundError(str(session_id))
    return session


async def get_session_messages(db: AsyncSession, user_id: UUID, session_id: UUID) -> list[ChatMessage]:
    await _get_owned_session(db, user_id, session_id)
    stmt = (
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


def _rows_to_messages(rows: list[ChatMessage]) -> list[BaseMessage]:
    """Reconstructs the LangChain message sequence from persisted rows — a direct 1:1
    replay with no custom serialization format, since each row already mirrors exactly
    one HumanMessage/AIMessage/ToolMessage (see models/chat.py's docstring)."""
    messages: list[BaseMessage] = []
    for row in rows:
        if row.role == ChatRole.USER:
            messages.append(HumanMessage(content=row.content))
        elif row.role == ChatRole.ASSISTANT:
            messages.append(AIMessage(content=row.content, tool_calls=row.tool_calls or []))
        else:  # ChatRole.TOOL
            messages.append(
                ToolMessage(content=row.content, tool_call_id=row.tool_call_id or "", name=row.tool_name)
            )
    return messages


async def stream_turn(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    user_message: str,
    *,
    provider_override: ChatProvider | None = None,
) -> AsyncIterator[ChatSSEEvent]:
    session = await _get_owned_session(db, user.id, session_id)

    human_row = ChatMessage(session_id=session.id, role=ChatRole.USER, content=user_message)
    db.add(human_row)
    await db.commit()
    await db.refresh(human_row)

    yield ChatSSEEvent(
        "session_meta", {"session_id": str(session.id), "user_message_id": str(human_row.id)}
    )

    history = _rows_to_messages(await get_session_messages(db, user.id, session_id))

    chat_provider = provider_override or user.chat_provider
    new_messages: list[BaseMessage] = []

    try:
        provider = await get_provider(db, user.id, ProviderName(chat_provider.value), purpose="chat")
        tools = build_tools(db, user.id)
        profile_context = await build_context_digest(db, user.id)
        system_prompt = build_chatbot_system_prompt(
            preemptive_suggestions=user.chatbot_preemptive_github_suggestions,
            display_name=user.chat_display_name,
            profile_context=profile_context,
        )

        async for graph_event in stream_chat(
            provider,
            chat_provider=chat_provider,
            system_prompt=system_prompt,
            user_id=user.id,
            messages=history,
            tools=tools,
        ):
            if graph_event["type"] == "token":
                yield ChatSSEEvent("token", {"delta": graph_event["delta"]})
            elif graph_event["type"] == "tool_start":
                name = graph_event["name"]
                yield ChatSSEEvent(
                    "tool_start",
                    {
                        "tool_call_id": graph_event["tool_call_id"],
                        "name": name,
                        "label": TOOL_LABELS.get(name, f"Using {name}…"),
                    },
                )
            elif graph_event["type"] == "tool_end":
                yield ChatSSEEvent(
                    "tool_end",
                    {
                        "tool_call_id": graph_event["tool_call_id"],
                        "name": graph_event["name"],
                        "result": graph_event["result"],
                    },
                )
            elif graph_event["type"] == "final":
                new_messages = graph_event["messages"]
    except ProviderError as exc:
        yield ChatSSEEvent("error", {"code": exc.code, "message": exc.message})
        return
    except Exception as exc:  # noqa: BLE001 — a chat turn must never hang the SSE stream open
        yield ChatSSEEvent("error", {"code": "UNEXPECTED_ERROR", "message": str(exc)})
        return

    final_message_id = await _persist_turn(db, session, user_message, new_messages)
    yield ChatSSEEvent("done", {"message_id": str(final_message_id) if final_message_id else None})


async def _persist_turn(
    db: AsyncSession, session: ChatSession, user_message: str, messages: list[BaseMessage]
) -> UUID | None:
    last_assistant_id: UUID | None = None
    for message in messages:
        if isinstance(message, AIMessage):
            row = ChatMessage(
                session_id=session.id,
                role=ChatRole.ASSISTANT,
                content=message.content or "",
                tool_calls=message.tool_calls or None,
            )
            db.add(row)
            await db.flush()
            last_assistant_id = row.id
        elif isinstance(message, ToolMessage):
            db.add(
                ChatMessage(
                    session_id=session.id,
                    role=ChatRole.TOOL,
                    content=str(message.content),
                    tool_call_id=message.tool_call_id,
                    tool_name=message.name,
                    tool_result=getattr(message, "artifact", None),
                )
            )

    if session.title == "New chat":
        session.title = user_message[:60]
    session.last_message_at = datetime.now(UTC)
    await db.commit()
    return last_assistant_id
