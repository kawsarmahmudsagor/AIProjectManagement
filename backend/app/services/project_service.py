from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.richtext import html_to_text, sanitize_html
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectSection, ProjectUpdate


def _apply_section(project: Project, field: str, section: ProjectSection) -> None:
    long_html = sanitize_html(section.long.html)
    short_html = sanitize_html(section.short.html)
    setattr(project, f"{field}_long_html", long_html)
    setattr(project, f"{field}_long_text", html_to_text(long_html))
    setattr(project, f"{field}_short_html", short_html)
    setattr(project, f"{field}_short_text", html_to_text(short_html))


async def create_project(db: AsyncSession, user_id: UUID, payload: ProjectCreate) -> Project:
    project = Project(
        user_id=user_id,
        name=payload.name,
        role=payload.role,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_current=payload.is_current,
        technologies=payload.technologies,
        project_url=payload.project_url,
    )
    _apply_section(project, "description", payload.description)
    _apply_section(project, "responsibilities", payload.responsibilities)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


async def update_project(db: AsyncSession, project: Project, payload: ProjectUpdate) -> Project:
    data = payload.model_dump(exclude_unset=True)

    for field in ("name", "role", "start_date", "end_date", "is_current", "technologies", "project_url"):
        if field in data:
            setattr(project, field, data[field])

    if payload.description is not None:
        _apply_section(project, "description", payload.description)
    if payload.responsibilities is not None:
        _apply_section(project, "responsibilities", payload.responsibilities)

    if project.is_current:
        project.end_date = None

    await db.commit()
    await db.refresh(project)
    return project


async def get_project(db: AsyncSession, user_id: UUID, project_id: UUID) -> Project | None:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def list_projects(
    db: AsyncSession, user_id: UUID, *, q: str | None, page: int, page_size: int, technology: str | None = None
) -> tuple[list[Project], int]:
    query = select(Project).where(Project.user_id == user_id)
    count_query = select(func.count()).select_from(Project).where(Project.user_id == user_id)

    if q:
        pattern = f"%{q}%"
        query = query.where(Project.name.ilike(pattern))
        count_query = count_query.where(Project.name.ilike(pattern))

    if technology:
        # Case-insensitive match against the free-text `technologies` array — filtered in
        # Python rather than a correlated unnest() subquery, same reasoning and same
        # documented scale assumption as agents/chat_tools.py's project_search tool
        # (tens to low hundreds of rows per user). Pagination therefore also happens in
        # Python for this branch, since the SQL-level LIMIT/OFFSET can't know the
        # post-filter count in advance.
        wanted = technology.lower()
        all_rows = (await db.execute(query.order_by(Project.updated_at.desc()))).scalars().all()
        matched = [p for p in all_rows if wanted in {t.lower() for t in p.technologies}]
        total = len(matched)
        start = (page - 1) * page_size
        return matched[start : start + page_size], total

    total = (await db.execute(count_query)).scalar_one()
    query = query.order_by(Project.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return list(items), total


async def delete_project(db: AsyncSession, project: Project) -> None:
    await db.delete(project)
    await db.commit()
