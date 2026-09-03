from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.schemas.chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatSessionListResponse,
    ChatSessionOut,
    ChatSessionStarUpdate,
    ChatSSEEvent,
)
from app.services import chat_service
from app.services.chat_service import ChatSessionNotFoundError
from app.workers.settings import enqueue_compact_history, enqueue_generate_title

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_or_get_current_session(
    user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ChatSessionOut:
    """Idempotent by design — returns the user's existing current session (auto-inserting
    the greeting only the first time) rather than always creating a new one, so the
    frontend can call this unconditionally on first panel-open without a separate
    GET-then-create dance."""
    session = await chat_service.get_or_create_current_session(db, user)
    return ChatSessionOut.model_validate(session)


@router.post("/sessions/new", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_new_session(
    user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ChatSessionOut:
    """Unconditionally starts a brand-new conversation — the chat widget's "New chat"
    button — as opposed to POST /sessions above, which resumes whatever's most recent."""
    session = await chat_service.create_new_session(db, user)
    return ChatSessionOut.model_validate(session)


@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(
    q: str | None = Query(None),
    starred_only: bool = Query(False),
    sort: Literal["asc", "desc"] = Query("desc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionListResponse:
    sessions, total = await chat_service.list_sessions(
        db, user.id, q=q, starred_only=starred_only, sort=sort, page=page, page_size=page_size
    )
    return ChatSessionListResponse(
        items=[ChatSessionOut.model_validate(s) for s in sessions], total=total
    )


@router.patch("/sessions/{session_id}/star", response_model=ChatSessionOut)
async def star_session(
    session_id: UUID,
    payload: ChatSessionStarUpdate,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> ChatSessionOut:
    # ChatSessionNotFoundError subclasses ResourceNotFoundError — the app-wide handler in
    # main.py turns it into a 404, so no try/except is needed here.
    session = await chat_service.set_starred(db, user.id, session_id, payload.starred)
    return ChatSessionOut.model_validate(session)


@router.post("/sessions/{session_id}/activate", response_model=ChatSessionOut)
async def activate_session(
    session_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> ChatSessionOut:
    session = await chat_service.activate_session(db, user.id, session_id)
    return ChatSessionOut.model_validate(session)


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(
    session_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ChatMessageOut]:
    messages = await chat_service.get_session_messages(db, user.id, session_id)
    return [ChatMessageOut.model_validate(m) for m in messages]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    await chat_service.delete_session(db, user.id, session_id)


@router.post("/sessions/{session_id}/messages")
async def post_message(
    session_id: UUID,
    payload: ChatMessageIn,
    user: User = CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    async def event_source():
        try:
            async for event in chat_service.stream_turn(
                db, user, session_id, payload.content, provider_override=payload.provider
            ):
                yield event.to_sse()
        except ChatSessionNotFoundError:
            yield ChatSSEEvent(
                "error", {"code": "NOT_FOUND", "message": "Chat session not found"}
            ).to_sse()
            return

        # Fire-and-forget maintenance, kept out of chat_service (which stays
        # queue-agnostic per DESIGN.md §6) and run after the SSE stream has already
        # yielded "done" so neither adds perceived latency to the turn itself.
        if await chat_service.needs_title_generation(db, user.id, session_id):
            await enqueue_generate_title(session_id)
        if await chat_service.unsummarized_message_count(db, user.id, session_id) > chat_service.COMPACTION_THRESHOLD:
            await enqueue_compact_history(session_id)

    # media_type must stay uncompressed end-to-end (no gzip middleware, no buffering
    # reverse proxy) or "streams live" silently becomes "arrives in one chunk" — see the
    # plan's Part F risk #5.
    return StreamingResponse(event_source(), media_type="text/event-stream")
