from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.providers.base import ProviderError
from app.schemas.profile import (
    ENHANCEABLE_FIELDS,
    PhotoUploadResponse,
    ProfileEnhanceRequest,
    ProfileEnhanceResponse,
    ProfileOut,
    ProfileUpdate,
)
from app.services import profile_service
from app.services.profile_service import PhotoTooLargeError, UnsupportedPhotoFormatError

router = APIRouter(prefix="/profile", tags=["profile"])


def _to_profile_out(user: User, profile) -> ProfileOut:
    return ProfileOut(
        photo_url="/api/v1/profile/photo" if profile.photo_path else None,
        designation=profile.designation,
        team=profile.team,
        organization=profile.organization,
        speciality=profile.speciality,
        primary_skills=profile.primary_skills,
        secondary_skills=profile.secondary_skills,
        professional_biography=profile.professional_biography,
        work_experience_summary=profile.work_experience_summary,
        career_objective=profile.career_objective,
        key_strengths=profile.key_strengths,
        responsibilities=profile.responsibilities,
        first_name=user.first_name,
        middle_name=user.middle_name,
        last_name=user.last_name,
        preferred_name=user.preferred_name,
    )


@router.get("", response_model=ProfileOut)
async def get_profile(user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> ProfileOut:
    profile = await profile_service.get_or_create_profile(db, user.id)
    return _to_profile_out(user, profile)


@router.patch("", response_model=ProfileOut)
async def update_profile(
    payload: ProfileUpdate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProfileOut:
    updates = payload.model_dump(exclude_unset=True)
    profile = await profile_service.update_profile(db, user, updates)
    return _to_profile_out(user, profile)


@router.post("/enhance", response_model=ProfileEnhanceResponse)
async def enhance_field(
    payload: ProfileEnhanceRequest, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProfileEnhanceResponse:
    if payload.field not in ENHANCEABLE_FIELDS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"'{payload.field}' is not enhanceable")
    try:
        text = await profile_service.enhance_field(
            db, user, payload.field, payload.target_text, payload.instruction
        )
    except ProviderError as exc:
        raise HTTPException(422, {"code": exc.code, "message": exc.message}) from exc
    return ProfileEnhanceResponse(text=text)


@router.get("/photo")
async def get_photo(user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> FileResponse:
    profile = await profile_service.get_or_create_profile(db, user.id)
    if not profile.photo_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No photo set")
    return FileResponse(profile.photo_path)


@router.post("/photo", response_model=PhotoUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_photo(
    file: UploadFile = File(...), user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> PhotoUploadResponse:
    data = await file.read()
    try:
        await profile_service.save_photo(db, user.id, data)
    except UnsupportedPhotoFormatError as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from exc
    except PhotoTooLargeError as exc:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, str(exc)) from exc
    return PhotoUploadResponse(photo_url="/api/v1/profile/photo")


@router.delete("/photo", status_code=status.HTTP_204_NO_CONTENT)
async def delete_photo(user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> None:
    await profile_service.delete_photo(db, user.id)
