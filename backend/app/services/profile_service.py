"""CRUD for the /profile page plus the two places it touches other features:
- enhance_field(): reuses the existing rewrite_graph/run_rewrite machinery (the same one
  ai_service.rewrite_field calls for project fields) rather than inventing a parallel
  prompt path — see providers/prompts.PROFILE_FIELD_OPS.
- build_context_digest(): the only place Profile data touches Jarvis. Returns None when
  the profile is empty so the chatbot system prompt omits the section entirely (see
  providers/prompts.build_chatbot_system_prompt) rather than including an empty/placeholder
  block — an unfilled profile must never degrade the chatbot.
"""

import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.rewrite_graph import run_rewrite
from app.core.config import Settings, get_settings
from app.models.profile import UserProfile
from app.models.user import User
from app.providers.base import LLMProvider, ProviderError
from app.providers.prompts import PROFILE_FIELD_OPS
from app.providers.registry import get_provider

_IMAGE_MAGIC = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    # WEBP: "RIFF" .... "WEBP" — the 4-byte size field in between varies per file.
}
_MAX_PHOTO_BYTES = 5 * 1024 * 1024


class UnsupportedPhotoFormatError(Exception):
    pass


class PhotoTooLargeError(Exception):
    pass


def _sniff_image_mime_type(data: bytes) -> str:
    for magic, mime in _IMAGE_MAGIC.items():
        if data.startswith(magic):
            return mime
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise UnsupportedPhotoFormatError("Only JPEG, PNG, or WEBP images are supported")


async def get_or_create_profile(db: AsyncSession, user_id: UUID) -> UserProfile:
    """Defensive fallback only — every user gets a profile row at registration
    (routers/auth.register). This exists so a pre-existing/edge-case user without one
    still gets GET /profile working rather than a 500."""
    stmt = select(UserProfile).where(UserProfile.user_id == user_id)
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is None:
        profile = UserProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
    return profile


async def update_profile(db: AsyncSession, user: User, updates: dict) -> UserProfile:
    """`updates` is the incoming ProfileUpdate payload as a dict (exclude_unset) — name
    fields (first_name/middle_name/last_name/preferred_name) are written onto `user`,
    everything else onto `user`'s UserProfile row, in one transaction."""
    profile = await get_or_create_profile(db, user.id)

    name_fields = {"first_name", "middle_name", "last_name", "preferred_name"}
    for field, value in updates.items():
        if field in name_fields:
            setattr(user, field, value)
        else:
            setattr(profile, field, value)

    await db.commit()
    await db.refresh(profile)
    await db.refresh(user)
    return profile


async def enhance_field(db: AsyncSession, user: User, field: str, target_text: str) -> str:
    if field not in PROFILE_FIELD_OPS:
        raise ProviderError("INVALID_FIELD", f"'{field}' is not an enhanceable profile field")

    op, char_limit = PROFILE_FIELD_OPS[field]
    profile = await get_or_create_profile(db, user.id)

    provider: LLMProvider = await get_provider(db, user.id, None, purpose="rewrite")
    context = {
        "designation": profile.designation,
        "team": profile.team,
        "organization": profile.organization,
        "speciality": profile.speciality,
        "primary_skills": profile.primary_skills,
        "secondary_skills": profile.secondary_skills,
    }
    draft = await run_rewrite(
        provider,
        user.agent_persona,
        op=op,
        target_text=target_text,
        source_text=target_text,
        char_limit=char_limit,
        context=context,
        instruction=None,
    )
    return draft.strip()


def _photo_path(settings: Settings, user_id: UUID, ext: str) -> Path:
    photo_dir = settings.data_dir / "profile_photos" / str(user_id)
    photo_dir.mkdir(parents=True, exist_ok=True)
    return photo_dir / f"{uuid.uuid4()}{ext}"


async def save_photo(db: AsyncSession, user_id: UUID, data: bytes) -> UserProfile:
    if len(data) > _MAX_PHOTO_BYTES:
        raise PhotoTooLargeError(f"Photo exceeds the {_MAX_PHOTO_BYTES // (1024 * 1024)}MB limit")

    mime_type = _sniff_image_mime_type(data)
    ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime_type]

    profile = await get_or_create_profile(db, user_id)
    settings = get_settings()
    path = _photo_path(settings, user_id, ext)
    path.write_bytes(data)

    old_path = profile.photo_path
    profile.photo_path = str(path)
    await db.commit()
    await db.refresh(profile)

    if old_path:
        Path(old_path).unlink(missing_ok=True)
    return profile


async def delete_photo(db: AsyncSession, user_id: UUID) -> None:
    profile = await get_or_create_profile(db, user_id)
    if profile.photo_path:
        Path(profile.photo_path).unlink(missing_ok=True)
        profile.photo_path = None
        await db.commit()


async def build_context_digest(db: AsyncSession, user_id: UUID) -> str | None:
    profile = await get_or_create_profile(db, user_id)
    if profile.is_empty():
        return None

    lines = []
    if profile.designation:
        lines.append(f"Designation: {profile.designation}")
    if profile.team:
        lines.append(f"Team: {profile.team}")
    if profile.organization:
        lines.append(f"Organization: {profile.organization}")
    if profile.speciality:
        lines.append(f"Speciality: {profile.speciality}")
    if profile.primary_skills:
        lines.append(f"Primary skills: {', '.join(profile.primary_skills)}")
    if profile.secondary_skills:
        lines.append(f"Secondary skills: {', '.join(profile.secondary_skills)}")
    if profile.professional_biography:
        lines.append(f"Professional biography: {profile.professional_biography}")
    if profile.work_experience_summary:
        lines.append(f"Work experience summary: {profile.work_experience_summary}")
    if profile.career_objective:
        lines.append(f"Career objective: {profile.career_objective}")
    if profile.key_strengths:
        lines.append(f"Key strengths: {profile.key_strengths}")
    if profile.responsibilities:
        lines.append(f"Responsibilities: {profile.responsibilities}")
    return "\n".join(lines)
