from enum import StrEnum

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class AgentPersona(StrEnum):
    BUSINESS_ANALYST = "business_analyst"
    TECHNICAL_DEVELOPER = "technical_developer"


# Shared SQLAlchemy Enum instance, same reasoning as provider_name_enum in
# ai_provider_setting.py — declared once so the Postgres enum TYPE isn't emitted twice.
agent_persona_enum = Enum(AgentPersona, name="agent_persona")


class User(Base, UUIDPk, Timestamps):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    agent_persona: Mapped[AgentPersona] = mapped_column(
        agent_persona_enum, default=AgentPersona.BUSINESS_ANALYST, nullable=False
    )

    projects: Mapped[list["Project"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
    ai_provider_settings: Mapped[list["AIProviderSetting"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )
