from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.schemas.dashboard import DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    top_technologies: int = Query(default=30, ge=1, le=200),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    return await dashboard_service.build_summary(db, user.id, top_technologies=top_technologies)
