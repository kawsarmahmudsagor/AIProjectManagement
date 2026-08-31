from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectListResponse, ProjectOut, ProjectSummary, ProjectUpdate
from app.services import project_service
from app.workers.settings import enqueue_suggestion_recompute

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_out(project) -> ProjectOut:
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
    )


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ProjectListResponse:
    items, total = await project_service.list_projects(db, user.id, q=q, page=page, page_size=page_size)
    summaries = [
        ProjectSummary(
            id=p.id,
            name=p.name,
            role=p.role,
            start_date=p.start_date,
            end_date=p.end_date,
            is_current=p.is_current,
            short_summary_text=p.description_short_text,
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
    return _to_out(project)


async def _get_owned_project(project_id: UUID, user: User, db: AsyncSession):
    project = await project_service.get_project(db, user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return project


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(
    project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await _get_owned_project(project_id, user, db)
    return _to_out(project)


@router.patch("/{project_id}", response_model=ProjectOut)
async def update_project(
    project_id: UUID, payload: ProjectUpdate, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ProjectOut:
    project = await _get_owned_project(project_id, user, db)
    tech_changed = payload.technologies is not None and (
        {t.lower() for t in payload.technologies} != {t.lower() for t in project.technologies}
    )
    project = await project_service.update_project(db, project, payload)
    if user.chatbot_preemptive_github_suggestions and tech_changed:
        await enqueue_suggestion_recompute(user.id)
    return _to_out(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    project = await _get_owned_project(project_id, user, db)
    had_technologies = bool(project.technologies)
    await project_service.delete_project(db, project)
    if user.chatbot_preemptive_github_suggestions and had_technologies:
        await enqueue_suggestion_recompute(user.id)
