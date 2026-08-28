import uuid
from enum import StrEnum

from sqlalchemy import Boolean, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk


class ProviderName(StrEnum):
    GEMINI = "gemini"
    OLLAMA = "ollama"


# Shared SQLAlchemy Enum instance — reused by extraction_job.py so the "provider_name"
# Postgres enum TYPE is only ever declared once in metadata (two separate `Enum(...)`
# objects with the same `name` would otherwise emit CREATE TYPE twice on create_all).
provider_name_enum = Enum(ProviderName, name="provider_name")


class AIProviderSetting(Base, UUIDPk, Timestamps):
    """Per-user provider config. encrypted_api_key is Fernet-ciphertext (app.core.security)
    — required for gemini, optional for ollama (only needed if base_url points at Ollama
    Cloud for non-extraction chat use; extraction itself is local-only, see DESIGN.md §4).
    """

    __tablename__ = "ai_provider_settings"
    __table_args__ = (UniqueConstraint("user_id", "provider", name="uq_user_provider"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[ProviderName] = mapped_column(provider_name_enum, nullable=False)

    encrypted_api_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user: Mapped["User"] = relationship(back_populates="ai_provider_settings")  # noqa: F821
