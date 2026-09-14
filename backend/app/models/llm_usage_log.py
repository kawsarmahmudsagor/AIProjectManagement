import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.ai_provider_setting import ProviderName, provider_name_enum
from app.models.base import UUIDPk


class LLMUsageLog(Base, UUIDPk):
    """One row per completed LLM call, written by services/usage_service.record_usage —
    the only place in the app that answers "how many tokens has this user actually
    burned, and on what". Covers every provider call site (chat turns, title
    generation, history compaction, document extraction, field rewrite, task
    breakdown, brag document generation), tagged by `operation`. Write-only from the
    app's own code today — no read endpoint yet; query this table directly for
    cost/usage analysis until a reporting surface is built.

    `session_id` is nullable with ON DELETE SET NULL (not CASCADE) — deleting a chat
    session must not erase its cost history, same reasoning as
    ChatSession.summarized_through_message_id's own SET NULL.
    """

    __tablename__ = "llm_usage_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="SET NULL"), nullable=True
    )
    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    # Free-form, not a DB enum — this set will grow (new tools/jobs) and only this
    # app's own code ever writes it, same precedent as BreakdownJob.error_code.
    operation: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
