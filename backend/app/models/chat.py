"""Persisted chat history for Jarvis (the Project Intelligence & Technology Advisor
chatbot). One row per LangChain message: HumanMessage -> role=user, AIMessage ->
role=assistant (+tool_calls when it requested tool calls), ToolMessage -> role=tool
(+tool_name/tool_call_id/tool_result). This 1:1 mapping is deliberate — it makes replaying
history back into the LangGraph state on the next turn a plain ordered SELECT, with no
custom serialization format to invent, and tool_result is stored as structured JSONB (not
rendered text) so the frontend can re-render rich cards (e.g. GitHub repo suggestions) on
reload without re-parsing anything.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Identity, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class ChatRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


chat_role_enum = Enum(ChatRole, name="chat_role")


class ChatSession(Base, UUIDPk, Timestamps):
    """Multiple sessions per user are supported in the schema (a session list/switcher is
    a natural follow-on), but v1's frontend only ever operates on "the user's most recent
    session, auto-created on first open" — no switcher UI yet."""

    __tablename__ = "chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), default="New chat", nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    starred: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Rolling context-window compaction (see chat_service.py's _build_history /
    # compact_history): once a session accumulates enough raw messages, the older ones
    # are periodically folded into context_summary and summarized_through_message_id
    # marks the cutoff, so future turns replay [summary] + [raw messages after cutoff]
    # to the LLM instead of the full history. Purely an LLM-context optimization — the
    # raw ChatMessage rows are never touched and the UI always renders them in full.
    context_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summarized_through_message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="chat_sessions")  # noqa: F821
    # foreign_keys pinned explicitly: summarized_through_message_id above is a second FK
    # linking chat_sessions <-> chat_messages, so SQLAlchemy can no longer infer which
    # column this relationship's join condition should use.
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.sequence",
        foreign_keys="ChatMessage.session_id",
    )


class ChatMessage(Base, UUIDPk, Timestamps):
    __tablename__ = "chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Strictly increasing insertion-order marker for replay/compaction ordering.
    # created_at can't serve this role: Postgres's now()/CURRENT_TIMESTAMP is fixed for
    # the whole transaction, so every message persisted in one turn (an assistant reply
    # plus its tool messages) shares an identical created_at, and the (random) UUID id
    # has no relationship to insertion order either.
    sequence: Mapped[int] = mapped_column(BigInteger, Identity(), nullable=False, unique=True, index=True)
    role: Mapped[ChatRole] = mapped_column(chat_role_enum, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Populated only on assistant messages that made tool calls this turn: a list of
    # {tool_call_id, name, args} mirroring LangChain's AIMessage.tool_calls.
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB, nullable=True)
    # Populated only on role=tool messages, pairing back to the tool_calls entry above.
    tool_call_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="messages", foreign_keys=[session_id])
