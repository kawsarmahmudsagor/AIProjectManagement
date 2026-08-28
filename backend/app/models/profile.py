"""User Profile: CV-style content (photo, designation/team/organization, skills,
speciality, and a handful of AI-enhanced bio sections) shown on the /profile page.

A separate table from `users` — auth/preference concerns stay on User (same reasoning
ai_provider_settings already uses for connection config), while this table holds richer,
optional content. Every column here except the FK is optional: an empty profile must never
degrade or block the rest of the app, including Jarvis (see providers/prompts.py's
build_chatbot_system_prompt and services/profile_service.build_context_digest).

Bio fields are plain text, NOT the {html,text} RichText pair used for Project fields — the
reference design has no bold/italic/list toolbar on these boxes, so there's no rich-text
editor involved, just a plain textarea + "Enhance with AI" suggestion panel.
"""

import uuid

from sqlalchemy import ARRAY, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Timestamps, UUIDPk

# Char caps for the five AI-enhanced bio fields — enforced both client-side and by the
# generate-then-verify-retry loop in services/profile_service.enhance_field (mirrors
# ai_service.rewrite_field's existing 390-char loop for project short summaries).
PROFESSIONAL_BIOGRAPHY_LIMIT = 550
WORK_EXPERIENCE_SUMMARY_LIMIT = 390
CAREER_OBJECTIVE_LIMIT = 390
KEY_STRENGTHS_LIMIT = 390
RESPONSIBILITIES_LIMIT = 390


class UserProfile(Base, UUIDPk, Timestamps):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    photo_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(150), nullable=True)
    team: Mapped[str | None] = mapped_column(String(150), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(150), nullable=True)
    speciality: Mapped[str | None] = mapped_column(String(150), nullable=True)

    primary_skills: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, nullable=False)
    secondary_skills: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list, nullable=False)

    professional_biography: Mapped[str] = mapped_column(Text, default="", nullable=False)
    work_experience_summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    career_objective: Mapped[str] = mapped_column(Text, default="", nullable=False)
    key_strengths: Mapped[str] = mapped_column(Text, default="", nullable=False)
    responsibilities: Mapped[str] = mapped_column(Text, default="", nullable=False)

    user: Mapped["User"] = relationship(back_populates="profile")  # noqa: F821

    def is_empty(self) -> bool:
        """True when every optional field is unset — drives whether Jarvis's system
        prompt includes a profile-context section at all (see
        services/profile_service.build_context_digest)."""
        return not any(
            [
                self.designation,
                self.team,
                self.organization,
                self.speciality,
                self.primary_skills,
                self.secondary_skills,
                self.professional_biography,
                self.work_experience_summary,
                self.career_objective,
                self.key_strengths,
                self.responsibilities,
            ]
        )
