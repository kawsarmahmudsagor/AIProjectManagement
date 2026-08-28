from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.services import project_service
from app.services.export_service import export_project

router = APIRouter(prefix="/projects", tags=["export"])


@router.get("/{project_id}/export")
async def export(
    project_id: UUID,
    request: Request,
    format: str = Query(pattern="^(pdf|docx)$"),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> Response:
    project = await project_service.get_project(db, user.id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")

    browser = getattr(request.app.state, "browser", None)
    content, content_type, filename = await export_project(project, format, browser)

    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
