from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser
from app.models.user import User
from app.schemas.chat import ChatMessageIn, ChatMessageOut, ChatSessionOut, ChatSSEEvent
from app.services import chat_service
from app.services.chat_service import ChatSessionNotFoundError

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


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(user: User = CurrentUser, db: AsyncSession = Depends(get_db)) -> list[ChatSessionOut]:
    sessions = await chat_service.list_sessions(db, user.id)
    return [ChatSessionOut.model_validate(s) for s in sessions]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(
    session_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> list[ChatMessageOut]:
    try:
        messages = await chat_service.get_session_messages(db, user.id, session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat session not found") from exc
    return [ChatMessageOut.model_validate(m) for m in messages]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID, user: User = CurrentUser, db: AsyncSession = Depends(get_db)
) -> None:
    try:
        await chat_service.delete_session(db, user.id, session_id)
    except ChatSessionNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chat session not found") from exc


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

    # media_type must stay uncompressed end-to-end (no gzip middleware, no buffering
    # reverse proxy) or "streams live" silently becomes "arrives in one chunk" — see the
    # plan's Part F risk #5.
    return StreamingResponse(event_source(), media_type="text/event-stream")
