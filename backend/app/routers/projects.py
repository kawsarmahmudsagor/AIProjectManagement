from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.core.ownership import require_owned
from app.models.faq_job import FAQJob
from app.models.project import Project
from app.models.project_media import MediaKind
from app.models.user import User
from app.providers.registry import resolve_default_provider
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectOut, ProjectSummary, ProjectUpdate
from app.services import faq_service, project_media_service, project_service, video_frame_service
from app.workers.settings import enqueue_faq_generation, enqueue_suggestion_recompute

router = APIRouter(prefix="/projects", tags=["projects"])


async def _to_out(db: AsyncSession, user_id: UUID, project) -> ProjectOut:
    """Fetches this one project's media (at most 2 rows: thumbnail + video), its FAQ (if
    the background job has finished), and its extracted video frames (if any), and folds
    them into the response — see services/project_media_service.media_by_project for the
    batched form list_projects uses instead of calling this per row. FAQ/video-frames are
    single-project reads only (never batched into list_projects) since both only ever
    render on this one detail page."""
    media = await project_media_service.media_by_project(db, user_id, [project.id])
    row_media = media.get(project.id, {})
    faq_result = await faq_service.get_latest_result(db, project.id)
    frames = await video_frame_service.frames_by_project(db, user_id, project.id)
    return ProjectOut(
        id=project.id,
        name=project.name,
        role=project.role,
        start_date=project.start_date,
        end_date=project.end_date,
        is_current=project.is_current,
        description={
            "long": {"html": project.description_long_html, "text": project.description_long_text},
            "short": {"html": project.description_short_html, "text": project.description_short_text},
        },
        responsibilities={
            "long": {"html": project.responsibilities_long_html, "text": project.responsibilities_long_text},
            "short": {"html": project.responsibilities_short_html, "text": project.responsibilities_short_text},
        },
        technologies=project.technologies,
        project_url=project.project_url,
        created_at=project.created_at,
        updated_at=project.updated_at,
        thumbnail=project_media_service.media_ref(project.id, row_media.get(MediaKind.THUMBNAIL)),
        video=project_media_service.media_ref(project.id, row_media.get(MediaKind.VIDEO)),
        faq=faq_result.items if faq_result else [],
        video_frames=[video_frame_service.frame_ref(project.id, f) for f in frames],
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    q: str | None = Query(default=None),
    technology: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    items, total = await project_service.list_projects(
        db, user.id, q=q, page=page, page_size=page_size, technology=technology
    )
    # One batched media query for the whole page — never per-row (see
    # project_media_service.media_by_project's docstring).
    media = await project_media_service.media_by_project(db, user.id, [p.id for p in items])
    summaries = [
        ProjectSummary(
            id=p.id,
            name=p.name,
            role=p.role,
            start_date=p.start_date,
            end_date=p.end_date,
            is_current=p.is_current,
            short_summary_text=p.description_short_text,
            technologies=p.technologies,
            thumbnail_url=(ref.url if (ref := project_media_service.media_ref(p.id, media.get(p.id, {}).get(MediaKind.THUMBNAIL))) else None),
            video_url=(ref.url if (ref := project_media_service.media_ref(p.id, media.get(p.id, {}).get(MediaKind.VIDEO))) else None),
        )
        for p in items
    ]
    return ProjectListResponse(items=summaries, total=total)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await project_service.create_project(db, user.id, payload)
    if user.chatbot_preemptive_github_suggestions and project.technologies:
        await enqueue_suggestion_recompute(user.id)

    # Unconditional — unlike the suggestion recompute above, FAQ generation has no
    # user-facing toggle or "Generate" action anywhere: it's an invisible implementation
    # detail (see services/faq_service.py's docstring), so every new project gets one.
    faq_provider = await resolve_default_provider(db, user.id)
    faq_job = FAQJob(user_id=user.id, project_id=project.id, provider=faq_provider)
    db.add(faq_job)
    await db.commit()
    await enqueue_faq_generation(faq_job.id)

    return await _to_out(db, user.id, project)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await require_owned(db, Project, project_id, user.id, resource="Project")
    return await _to_out(db, user.id, project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID, payload: ProjectUpdate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await require_owned(db, Project, project_id, user.id, resource="Project")
    tech_changed = payload.technologies is not None and (
        {t.lower() for t in payload.technologies} != {t.lower() for t in project.technologies}
    )
    project = await project_service.update_project(db, project, payload)
    if user.chatbot_preemptive_github_suggestions and tech_changed:
        await enqueue_suggestion_recompute(user.id)
    return await _to_out(db, user.id, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    project = await require_owned(db, Project, project_id, user.id, resource="Project")
    had_technologies = bool(project.technologies)
    await project_service.delete_project(db, project)
    if user.chatbot_preemptive_github_suggestions and had_technologies:
        await enqueue_suggestion_recompute(user.id)
