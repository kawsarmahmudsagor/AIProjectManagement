from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ownership import owned
from app.models.project import Project
from app.models.project_media import MediaKind
from app.schemas.dashboard import DashboardSummary, TechnologyCount
from app.schemas.project import ProjectSummary
from app.services import project_media_service
from app.services.portfolio_service import technology_frequency_from_projects
from app.services.profile_service import get_or_create_profile


def _to_summary(p: Project, media: dict) -> ProjectSummary:
    thumb = project_media_service.media_ref(p.id, media.get(MediaKind.THUMBNAIL))
    video = project_media_service.media_ref(p.id, media.get(MediaKind.VIDEO))
    return ProjectSummary(
        id=p.id,
        name=p.name,
        role=p.role,
        start_date=p.start_date,
        end_date=p.end_date,
        is_current=p.is_current,
        short_summary_text=p.description_short_text,
        technologies=p.technologies,
        thumbnail_url=thumb.url if thumb else None,
        video_url=video.url if video else None,
    )


async def build_summary(db: AsyncSession, user_id: UUID, *, top_technologies: int = 30) -> DashboardSummary:
    """One pass over the user's projects, reusing portfolio_service's technology
    counting (the same implementation behind chat_tools.portfolio_analysis and the
    background suggestion job) rather than a second, drifting definition of "which
    skills does this person have". Uses the pure technology_frequency_from_projects with
    the list already loaded here, instead of compute_technology_frequency, which would
    re-SELECT the same rows."""
    projects = list(
        (
            await db.execute(
                owned(Project, user_id).order_by(Project.is_current.desc(), Project.start_date.desc())
            )
        )
        .scalars()
        .all()
    )

    freq = technology_frequency_from_projects(projects)
    media = await project_media_service.media_by_project(db, user_id, [p.id for p in projects])
    profile = await get_or_create_profile(db, user_id)

    return DashboardSummary(
        total_projects=len(projects),
        current_projects=sum(1 for p in projects if p.is_current),
        technologies=[TechnologyCount(**t) for t in freq["technologies"][:top_technologies]],
        distinct_technology_count=len(freq["technologies"]),
        primary_skills=profile.primary_skills or [],
        secondary_skills=profile.secondary_skills or [],
        projects=[_to_summary(p, media.get(p.id, {})) for p in projects],
    )
