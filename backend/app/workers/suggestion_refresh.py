"""Cron job: recomputes GitHub repo suggestions for users whose dashboard suggestions are
missing or stale (app/services/suggestion_service.py), catching up any user who hasn't
had a qualifying project edit recently enough to trigger the event-driven path."""

from app.core.database import async_session_factory
from app.services.suggestion_service import recompute_stale_suggestions


async def refresh_stale_suggestions(ctx) -> None:
    async with async_session_factory() as db:
        await recompute_stale_suggestions(db)
