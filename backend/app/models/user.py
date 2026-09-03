from enum import StrEnum

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class AgentPersona(StrEnum):
    BUSINESS_ANALYST = "business_analyst"
    TECHNICAL_DEVELOPER = "technical_developer"


class ChatProvider(StrEnum):
    """Which configured AI connection drives Jarvis (the chatbot) for this user.

    Deliberately a separate enum from ai_provider_setting.ProviderName even though the
    values match today: ProviderName describes a *configured connection* (base_url, key,
    default model); ChatProvider describes *which of those connections chat should use*.
    Keeping them distinct avoids coupling chat's provider choice to whatever connection
    concepts extraction/rewrite need later.
    """

    GEMINI = "gemini"
    OPENAI = "openai"


# Shared SQLAlchemy Enum instances, same reasoning as provider_name_enum in
# ai_provider_setting.py — declared once so the Postgres enum TYPE isn't emitted twice.
agent_persona_enum = Enum(AgentPersona, name="agent_persona")
chat_provider_enum = Enum(ChatProvider, name="chat_provider")


class User(Base, UUIDPk, Timestamps):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_persona: Mapped[AgentPersona] = mapped_column(
        agent_persona_enum, default=AgentPersona.BUSINESS_ANALYST, nullable=False
    )

    # Only first_name is required (at registration); the rest are always optional. Jarvis's
    # greeting uses preferred_name (falling back to first_name) — see User.chat_display_name
    # — never the full name, and never designation/team/etc. from the Profile (UserProfile).
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    middle_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    preferred_name: Mapped[str | None] = mapped_column(String(80), nullable=True)

    chat_provider: Mapped[ChatProvider] = mapped_column(
        chat_provider_enum, default=ChatProvider.GEMINI, nullable=False
    )
    chatbot_preemptive_github_suggestions: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_provider_settings: Mapped[list["AIProviderSetting"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    profile: Mapped["UserProfile"] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )
    chat_sessions: Mapped[list["ChatSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        """Fuller display name for contexts that want it (e.g. a user list) — never used
        for Jarvis's greeting, which uses chat_display_name instead."""
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)

    @property
    def chat_display_name(self) -> str:
        """The only name Jarvis's greeting ever uses — preferred_name if set, else
        first_name (which is guaranteed to exist). Never the full name, never
        designation/team/etc. from the Profile."""
        return self.preferred_name or self.first_name
