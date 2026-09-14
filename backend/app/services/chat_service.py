"""Orchestrates Jarvis's chat turns: session lifecycle, provider/tool/prompt resolution,
history replay, and persisting the new messages agents/chatbot_graph.stream_chat produces.
Mirrors ai_service.py's shape — plain async defs, db: AsyncSession, resolve the provider
via get_provider(), catch ProviderError explicitly plus a catch-all fallback so a chat
turn never hangs the SSE stream half-open.
"""

import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.chat_tools import TOOL_LABELS, build_tools
from app.agents.chatbot_graph import stream_chat
from app.agents.chatbot_graph import stringify_content as _stringify_content
from app.core.ownership import ResourceNotFoundError, owned
from app.ingest.extract import UnsupportedFormatError, ingest
from app.ingest.media_sniff import UnsupportedMediaFormatError, sniff_image_mime_type
from app.models.ai_provider_setting import ProviderName
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.chat_attachment import AttachmentKind, ChatAttachment, ChatAttachmentBlob
from app.models.user import ChatProvider, User
from app.providers.base import ProviderError
from app.providers.catalog import context_window_for
from app.providers.content_blocks import AttachmentPayload, build_user_content, image_placeholder_block
from app.providers.prompts import (
    build_chatbot_system_prompt,
    build_compaction_prompt,
    build_title_generation_prompt,
)
from app.providers.registry import get_provider, resolve_chat_model_name
from app.providers.tokens import estimate_tokens
from app.schemas.chat import ChatSSEEvent
from app.services.breakdown_service import _UNSAFE_CHARS_RE
from app.services.profile_service import build_context_digest
from app.services.usage_service import record_usage

# Per-attachment and per-turn caps on how much extracted document text gets injected as
# chat context — a 200-page PDF's full text would dwarf the conversation itself.
_MAX_ATTACHMENT_TEXT_CHARS = 100_000
# The N most recent images in the replayed window are sent as real image blocks; older
# ones become text placeholders (providers/content_blocks.image_placeholder_block). At
# max_chat_image_size_mb=5 and a 10-message unsummarized window, an unbounded version
# could hold 250MB of base64'd image data in one request — this is the sharpest edge of
# storing chat attachment bytes in the DB rather than on disk.
_MAX_REPLAYED_IMAGES = 4


class UnsupportedAttachmentFormatError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class AttachmentTooLargeError(Exception):
    pass


class AttachmentAlreadyUsedError(Exception):
    """Raised when deleting an attachment that's already bound to a persisted message —
    see delete_attachment's docstring."""

# Compaction thresholds for _build_history/compact_history below — see that function's
# docstring for the rolling-summary design. COMPACTION_THRESHOLD is now only the
# *fallback* trigger (see should_compact) — the primary trigger is token-based, sized
# against the user's actual configured model's context window.
COMPACTION_THRESHOLD = 50
COMPACTION_TOKEN_FRACTION = 0.5
_COMPACTION_KEEP_RECENT = 10


class ChatSessionNotFoundError(ResourceNotFoundError):
    """Subclasses ResourceNotFoundError so the app-wide 404 handler catches it via the
    exception's MRO — but keeps its own type so routers/chat.py's SSE generator can still
    catch it specifically (an exception handler can't help once a StreamingResponse has
    already started sending 200 OK + bytes)."""

    def __init__(self, session_id: UUID | str):
        super().__init__("Chat session", session_id)


async def _create_session_with_greeting(db: AsyncSession, user: User) -> ChatSession:
    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.flush()

    # Deterministic template greeting, never an LLM call — this is the one message every
    # single user always sees, so it can't misfire, hallucinate, or cost a token. Uses
    # only the user's chat display name (preferred name, else first name) — never the
    # full name, designation, team, or any Profile field.
    greeting = ChatMessage(
        session_id=session.id,
        role=ChatRole.ASSISTANT,
        content=(
            f"Hey {user.chat_display_name}! Jarvis here — think of me as your go-to "
            "for anything about your projects — I can dig through your work, spot tech "
            "patterns across it, or point you to solid open-source tools if you're "
            "exploring something new. Ask away, and I'll always stick to what's "
            "actually in your projects when I'm talking about your own work."
        ),
    )
    db.add(greeting)
    await db.commit()
    await db.refresh(session)
    return session


async def get_or_create_current_session(db: AsyncSession, user: User) -> ChatSession:
    """Returns the user's most recent session, or creates one — this is what the floating
    widget opens by default. Multiple sessions per user are fully supported (see
    create_new_session below and the /conversations page's resume flow); this just picks
    whichever one currently has the newest last_message_at."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user.id)
        .order_by(ChatSession.last_message_at.desc())
        .limit(1)
    )
    session = (await db.execute(stmt)).scalars().first()
    if session is not None:
        return session
    return await _create_session_with_greeting(db, user)


async def create_new_session(db: AsyncSession, user: User) -> ChatSession:
    """Unconditionally starts a brand-new conversation (the widget's "New chat" action),
    as opposed to get_or_create_current_session's "resume whatever's most recent"
    behavior. Since it's freshly created its last_message_at is the newest, so it
    immediately becomes the "current" session too."""
    return await _create_session_with_greeting(db, user)


async def list_sessions(
    db: AsyncSession,
    user_id: UUID,
    *,
    q: str | None = None,
    starred_only: bool = False,
    sort: Literal["asc", "desc"] = "desc",
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[ChatSession], int]:
    query = select(ChatSession).where(ChatSession.user_id == user_id)
    count_query = select(func.count()).select_from(ChatSession).where(ChatSession.user_id == user_id)

    if q:
        pattern = f"%{q}%"
        query = query.where(ChatSession.title.ilike(pattern))
        count_query = count_query.where(ChatSession.title.ilike(pattern))

    if starred_only:
        query = query.where(ChatSession.starred.is_(True))
        count_query = count_query.where(ChatSession.starred.is_(True))

    total = (await db.execute(count_query)).scalar_one()
    order = ChatSession.last_message_at.asc() if sort == "asc" else ChatSession.last_message_at.desc()
    query = query.order_by(order).offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(query)).scalars().all()
    return list(items), total


async def delete_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> None:
    session = await _get_owned_session(db, user_id, session_id)
    await db.delete(session)
    await db.commit()


async def set_starred(db: AsyncSession, user_id: UUID, session_id: UUID, starred: bool) -> ChatSession:
    session = await _get_owned_session(db, user_id, session_id)
    session.starred = starred
    await db.commit()
    await db.refresh(session)
    return session


async def activate_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> ChatSession:
    """Bumps last_message_at to now with no message changes, so this session becomes
    "current" again per get_or_create_current_session's `order_by(last_message_at.desc())`
    — how the frontend "resume this conversation in the chat widget" action works."""
    session = await _get_owned_session(db, user_id, session_id)
    session.last_message_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(session)
    return session


async def _get_owned_session(db: AsyncSession, user_id: UUID, session_id: UUID) -> ChatSession:
    stmt = owned(ChatSession, user_id).where(ChatSession.id == session_id)
    session = (await db.execute(stmt)).scalar_one_or_none()
    if session is None:
        raise ChatSessionNotFoundError(session_id)
    return session


async def get_session_messages(db: AsyncSession, user_id: UUID, session_id: UUID) -> list[ChatMessage]:
    await _get_owned_session(db, user_id, session_id)
    # Ordered by the monotonic `sequence` column, not created_at — see ChatMessage.sequence's
    # docstring for why created_at can't serve as a reliable ordering/tiebreak key here.
    # selectinload, never lazy: this runs on an async session, and a lazy load during
    # ChatMessageOut.model_validate would raise MissingGreenlet. It stays a metadata-only
    # load — the blob table (ChatAttachmentBlob) has no relationship to eager-load, by
    # models/chat_attachment.py's own rule.
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .options(selectinload(ChatMessage.attachments))
        .order_by(ChatMessage.sequence)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_attachment_payloads(
    db: AsyncSession, rows: list[ChatMessage], *, include_image_bytes: bool
) -> dict[UUID, list[AttachmentPayload]]:
    """Two queries for a whole history, never per-row: one for every user row's
    attachment metadata (rows already carry it via get_session_messages' selectinload,
    so this just reshapes it), one for the blobs of just the images that survive the
    _MAX_REPLAYED_IMAGES cap. `include_image_bytes=False` (should_compact/compact_history's
    call) skips the second query entirely — a token-estimate pass has no business paying
    to load image bytes it will never encode."""
    by_message: dict[UUID, list[AttachmentPayload]] = {}
    all_attachments: list[ChatAttachment] = []
    for row in rows:
        if row.role != ChatRole.USER or not row.attachments:
            continue
        all_attachments.extend(row.attachments)

    if not all_attachments:
        return {}

    image_ids_to_load: set[UUID] = set()
    if include_image_bytes:
        image_attachments = [a for a in all_attachments if a.kind == AttachmentKind.IMAGE]
        # Most-recent-first across the whole history, capped — matches "the N most
        # recent images survive" regardless of which message they're attached to.
        for a in sorted(image_attachments, key=lambda a: a.created_at, reverse=True)[:_MAX_REPLAYED_IMAGES]:
            image_ids_to_load.add(a.id)

    blob_by_id: dict[UUID, bytes] = {}
    if image_ids_to_load:
        blob_stmt = select(ChatAttachmentBlob.attachment_id, ChatAttachmentBlob.data).where(
            ChatAttachmentBlob.attachment_id.in_(image_ids_to_load)
        )
        for attachment_id, data in (await db.execute(blob_stmt)).all():
            blob_by_id[attachment_id] = bytes(data)

    for row in rows:
        if row.role != ChatRole.USER or not row.attachments:
            continue
        payloads: list[AttachmentPayload] = []
        for a in row.attachments:
            if a.kind == AttachmentKind.IMAGE:
                if a.id in blob_by_id:
                    payloads.append(
                        AttachmentPayload(id=a.id, filename=a.filename, mime_type=a.mime_type, kind=a.kind, data=blob_by_id[a.id])
                    )
                else:
                    # Either include_image_bytes=False, or this image aged out of the
                    # _MAX_REPLAYED_IMAGES window — represented as a placeholder further
                    # down in build_user_content's caller, not here (this function only
                    # reports what's loadable; content_blocks decides what to render).
                    payloads.append(AttachmentPayload(id=a.id, filename=a.filename, mime_type=a.mime_type, kind=a.kind))
            else:
                payloads.append(
                    AttachmentPayload(
                        id=a.id, filename=a.filename, mime_type=a.mime_type, kind=a.kind,
                        extracted_text=a.extracted_text, text_truncated=a.text_truncated,
                    )
                )
        by_message[row.id] = payloads
    return by_message


def _rows_to_messages(
    rows: list[ChatMessage], attachments: dict[UUID, list[AttachmentPayload]] | None = None
) -> list[BaseMessage]:
    """Reconstructs the LangChain message sequence from persisted rows — a direct 1:1
    replay with no custom serialization format, since each row already mirrors exactly
    one HumanMessage/AIMessage/ToolMessage (see models/chat.py's docstring).

    `attachments` (from _load_attachment_payloads) makes the USER branch conditional:
    with payloads in hand it reconstructs multimodal content via
    providers/content_blocks.build_user_content; otherwise (the default, and the only
    path should_compact/compact_history ever take — see their call sites) it falls back
    to today's plain-string content, so a token-estimate pass never pays to load images
    it will never encode."""
    messages: list[BaseMessage] = []
    for row in rows:
        if row.role == ChatRole.USER:
            payloads = (attachments or {}).get(row.id) or []
            if not payloads:
                messages.append(HumanMessage(content=row.content))
                continue

            # An image with no loaded bytes (either include_image_bytes=False upstream,
            # or it aged out of _MAX_REPLAYED_IMAGES) becomes a text placeholder instead
            # of silently vanishing from the replayed conversation.
            missing_images = [p for p in payloads if p.kind == AttachmentKind.IMAGE and p.data is None]
            real_payloads = [p for p in payloads if not (p.kind == AttachmentKind.IMAGE and p.data is None)]

            content = build_user_content(row.content, real_payloads)
            if missing_images:
                placeholders = [image_placeholder_block(p.filename) for p in missing_images]
                content = [*placeholders, *content] if isinstance(content, list) else [*placeholders, {"type": "text", "text": content}]
            messages.append(HumanMessage(content=content))
        elif row.role == ChatRole.ASSISTANT:
            messages.append(AIMessage(content=row.content, tool_calls=row.tool_calls or []))
        else:  # ChatRole.TOOL
            messages.append(
                ToolMessage(content=row.content, tool_call_id=row.tool_call_id or "", name=row.tool_name)
            )
    return messages


def _unsummarized_rows(session: ChatSession, rows: list[ChatMessage]) -> list[ChatMessage]:
    """Rows after session.summarized_through_message_id, found by position within `rows`
    rather than by comparing created_at — Postgres's now()/CURRENT_TIMESTAMP is fixed for
    the whole transaction, so every ChatMessage persisted in one turn shares an identical
    created_at, which breaks any timestamp-inequality cutoff. get_session_messages orders
    by (created_at, id), a stable total order, so "the boundary's index + 1 onward" is
    well-defined and consistent across separate calls."""
    if session.summarized_through_message_id is None:
        return rows
    boundary_index = next(
        (i for i, r in enumerate(rows) if r.id == session.summarized_through_message_id), None
    )
    return rows[boundary_index + 1 :] if boundary_index is not None else rows


def _build_history(
    session: ChatSession, rows: list[ChatMessage], attachments: dict[UUID, list[AttachmentPayload]] | None = None
) -> list[BaseMessage]:
    """Replays persisted rows into the LangChain message sequence sent to the LLM,
    applying rolling-summary compaction (see compact_history below): once
    session.summarized_through_message_id is set, only rows after that boundary are
    replayed, prefixed with one synthetic SystemMessage carrying session.context_summary.
    Rows in the DB and what the chat UI renders are untouched either way — this only
    shrinks what's sent to the LLM as context.

    `attachments` is None by default (should_compact never passes one — see its own
    call to _rows_to_messages directly, not through here) and only ever populated by
    stream_turn, which has a real provider in hand and needs the actual multimodal
    content reconstructed."""
    messages = _rows_to_messages(_unsummarized_rows(session, rows), attachments)
    if session.context_summary:
        messages = [
            SystemMessage(content=f"Summary of earlier conversation:\n\n{session.context_summary}"),
            *messages,
        ]
    return messages


async def needs_title_generation(db: AsyncSession, user_id: UUID, session_id: UUID) -> bool:
    session = await _get_owned_session(db, user_id, session_id)
    return session.title == "New chat"


async def should_compact(db: AsyncSession, user: User, session_id: UUID) -> bool:
    """Token-based replacement for a flat message-count threshold: gates
    compact_history on the estimated size of the unsummarized history relative to the
    user's *actual* configured chat model's context window, so a chatty session with
    large tool outputs (task lists, brag documents) compacts sooner than a plain-text
    session of the same length would. Falls back to the flat COMPACTION_THRESHOLD
    message count if the estimate or model lookup raises for any reason — a bug here
    can only make compaction run more often, never stop it from running at all."""
    session = await _get_owned_session(db, user.id, session_id)
    rows = _unsummarized_rows(session, await get_session_messages(db, user.id, session_id))
    if len(rows) <= _COMPACTION_KEEP_RECENT:
        return False

    try:
        token_count = estimate_tokens(_rows_to_messages(rows))
        provider_name = ProviderName(user.chat_provider.value)
        model = await resolve_chat_model_name(db, user.id, provider_name)
        budget = int(context_window_for(model) * COMPACTION_TOKEN_FRACTION)
        return token_count > budget
    except Exception:  # noqa: BLE001 — fall back rather than skip compaction entirely
        return len(rows) > COMPACTION_THRESHOLD


async def save_attachment(
    db: AsyncSession, user: User, session_id: UUID, *, filename: str, data: bytes, max_image_bytes: int, max_document_bytes: int
) -> ChatAttachment:
    """Pre-uploaded before the message it belongs to exists (message_id stays NULL until
    the turn is sent — see stream_turn's validation above) — see the plan's rationale for
    why this is pre-upload-then-reference rather than a multipart message endpoint: a
    retried/aborted SSE stream must not re-upload every byte, and FastAPI can't mix a
    Pydantic JSON body with File(...) in one route anyway.

    Tries image first, then falls back to ingest() (PDF/DOCX/text/code) — this is what
    makes code/text files "just work" for free: sniff_mime_type's UTF-8 fallback accepts
    any of .py/.ts/.json/.sql/.md with zero new code, and DOCX comes along the same way.
    A scanned PDF (no extractable text) is accepted anyway, with an explicit
    "no text could be extracted" marker at reconstruction time — silence there is what
    makes a model hallucinate contents.
    """
    await _get_owned_session(db, user.id, session_id)

    try:
        mime_type = sniff_image_mime_type(data)
        if len(data) > max_image_bytes:
            raise AttachmentTooLargeError(f"Image exceeds the {max_image_bytes // (1024 * 1024)}MB limit")
        attachment = ChatAttachment(
            user_id=user.id, session_id=session_id, kind=AttachmentKind.IMAGE,
            filename=filename[:255], mime_type=mime_type, size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
        )
    except UnsupportedMediaFormatError:
        if len(data) > max_document_bytes:
            raise AttachmentTooLargeError(f"File exceeds the {max_document_bytes // (1024 * 1024)}MB limit") from None
        try:
            parsed = ingest(data, filename)
        except UnsupportedFormatError as exc:
            raise UnsupportedAttachmentFormatError(exc.code, exc.message) from exc

        extracted = _UNSAFE_CHARS_RE.sub("", parsed.extracted_text or "")
        truncated = len(extracted) > _MAX_ATTACHMENT_TEXT_CHARS
        attachment = ChatAttachment(
            user_id=user.id, session_id=session_id, kind=AttachmentKind.DOCUMENT,
            filename=filename[:255], mime_type=parsed.mime_type, size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            extracted_text=extracted[:_MAX_ATTACHMENT_TEXT_CHARS],
            text_truncated=truncated,
        )

    db.add(attachment)
    await db.flush()
    db.add(ChatAttachmentBlob(attachment_id=attachment.id, data=data))
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def delete_attachment(db: AsyncSession, user_id: UUID, attachment_id: UUID) -> bool:
    """Idempotent (returns whether a row existed) like project_media_service.delete_media
    — EXCEPT once message_id is set: deleting an attachment a persisted message already
    replays would silently corrupt that message's history, so that case raises instead of
    quietly succeeding or quietly no-op'ing."""
    stmt = owned(ChatAttachment, user_id).where(ChatAttachment.id == attachment_id)
    attachment = (await db.execute(stmt)).scalar_one_or_none()
    if attachment is None:
        return False
    if attachment.message_id is not None:
        raise AttachmentAlreadyUsedError("This attachment is already part of a sent message.")
    await db.delete(attachment)
    await db.commit()
    return True


async def stream_turn(
    db: AsyncSession,
    user: User,
    session_id: UUID,
    user_message: str,
    *,
    provider_override: ChatProvider | None = None,
    attachment_ids: list[UUID] | None = None,
) -> AsyncIterator[ChatSSEEvent]:
    session = await _get_owned_session(db, user.id, session_id)

    # Every id must belong to this user AND this session AND not already be bound to a
    # different message — validated with one query, entirely before any message row is
    # created, so a bad id 404s cleanly instead of persisting a half-formed turn.
    if attachment_ids:
        stmt = select(ChatAttachment).where(
            ChatAttachment.id.in_(attachment_ids),
            ChatAttachment.user_id == user.id,
            ChatAttachment.session_id == session_id,
            ChatAttachment.message_id.is_(None),
        )
        found = list((await db.execute(stmt)).scalars().all())
        if len(found) != len(set(attachment_ids)):
            yield ChatSSEEvent(
                "error", {"code": "ATTACHMENT_NOT_FOUND", "message": "One of the attached files couldn't be found."}
            )
            return

    human_row = ChatMessage(session_id=session.id, role=ChatRole.USER, content=user_message)
    db.add(human_row)
    await db.flush()  # assigns human_row.id without ending the transaction

    if attachment_ids:
        # Bound in the same commit as the message row itself (the flush above just
        # allocates the id) — a crash between these two writes must never leave an
        # attachment pointing at a message that doesn't exist, or vice versa.
        for attachment in found:
            attachment.message_id = human_row.id

    await db.commit()
    await db.refresh(human_row)

    yield ChatSSEEvent(
        "session_meta", {"session_id": str(session.id), "user_message_id": str(human_row.id)}
    )

    rows = await get_session_messages(db, user.id, session_id)
    attachment_payloads = await _load_attachment_payloads(db, rows, include_image_bytes=True)
    history = _build_history(session, rows, attachment_payloads)

    chat_provider = provider_override or user.chat_provider
    new_messages: list[BaseMessage] = []

    try:
        provider = await get_provider(db, user.id, ProviderName(chat_provider.value), purpose="chat")
        tools = build_tools(db, user.id)
        profile_context = await build_context_digest(db, user.id)
        system_prompt = build_chatbot_system_prompt(
            preemptive_suggestions=user.chatbot_preemptive_github_suggestions,
            display_name=user.chat_display_name,
            profile_context=profile_context,
        )

        async for graph_event in stream_chat(
            provider,
            chat_provider=chat_provider,
            system_prompt=system_prompt,
            user_id=user.id,
            messages=history,
            tools=tools,
        ):
            if graph_event["type"] == "token":
                yield ChatSSEEvent("token", {"delta": graph_event["delta"]})
            elif graph_event["type"] == "tool_start":
                name = graph_event["name"]
                yield ChatSSEEvent(
                    "tool_start",
                    {
                        "tool_call_id": graph_event["tool_call_id"],
                        "name": name,
                        "label": TOOL_LABELS.get(name, f"Using {name}…"),
                    },
                )
            elif graph_event["type"] == "tool_end":
                yield ChatSSEEvent(
                    "tool_end",
                    {
                        "tool_call_id": graph_event["tool_call_id"],
                        "name": graph_event["name"],
                        "result": graph_event["result"],
                    },
                )
            elif graph_event["type"] == "final":
                new_messages = graph_event["messages"]
                for usage in graph_event.get("usage", []):
                    await record_usage(
                        db,
                        user_id=user.id,
                        session_id=session.id,
                        provider=ProviderName(chat_provider.value),
                        model=provider.model,
                        operation="chat",
                        usage=usage,
                    )
    except ProviderError as exc:
        yield ChatSSEEvent("error", {"code": exc.code, "message": exc.message})
        return
    except Exception as exc:  # noqa: BLE001 — a chat turn must never hang the SSE stream open
        yield ChatSSEEvent("error", {"code": "UNEXPECTED_ERROR", "message": str(exc)})
        return

    final_message_id = await _persist_turn(db, session, user_message, new_messages)
    yield ChatSSEEvent("done", {"message_id": str(final_message_id) if final_message_id else None})


async def _persist_turn(
    db: AsyncSession, session: ChatSession, user_message: str, messages: list[BaseMessage]
) -> UUID | None:
    last_assistant_id: UUID | None = None
    for message in messages:
        if isinstance(message, AIMessage):
            row = ChatMessage(
                session_id=session.id,
                role=ChatRole.ASSISTANT,
                content=_stringify_content(message.content) or "",
                tool_calls=message.tool_calls or None,
            )
            db.add(row)
            await db.flush()
            last_assistant_id = row.id
        elif isinstance(message, ToolMessage):
            db.add(
                ChatMessage(
                    session_id=session.id,
                    role=ChatRole.TOOL,
                    content=_stringify_content(message.content),
                    tool_call_id=message.tool_call_id,
                    tool_name=message.name,
                    tool_result=getattr(message, "artifact", None),
                )
            )

    session.last_message_at = datetime.now(UTC)
    await db.commit()
    return last_assistant_id


async def generate_session_title(db: AsyncSession, session_id: UUID) -> None:
    """Background job body (see workers/tasks.py's thin wrapper) — replaces a session's
    default "New chat" title with a short LLM-generated one based on its first exchange.
    No-ops if the session is gone or was already renamed since this job was enqueued
    (e.g. a duplicate enqueue from an overlapping turn), so it never clobbers a title
    the user or a later run already set."""
    session = await db.get(ChatSession, session_id)
    if session is None or session.title != "New chat":
        return

    rows = await get_session_messages(db, session.user_id, session_id)
    first_user = next((r for r in rows if r.role == ChatRole.USER), None)
    first_assistant = next((r for r in rows if r.role == ChatRole.ASSISTANT), None)
    if first_user is None or first_assistant is None:
        return

    user = await db.get(User, session.user_id)
    if user is None:
        return

    try:
        provider = await get_provider(db, user.id, ProviderName(user.chat_provider.value), purpose="chat_title")
        prompt = build_title_generation_prompt(first_user.content, first_assistant.content)
        response = await provider.get_chat_model().ainvoke([HumanMessage(content=prompt)])
    except Exception:  # noqa: BLE001 — a failed background title-gen must never crash the job
        return

    await record_usage(
        db,
        user_id=user.id,
        session_id=session.id,
        provider=ProviderName(user.chat_provider.value),
        model=provider.model,
        operation="chat_title",
        usage=getattr(response, "usage_metadata", None),
    )

    title = _stringify_content(response.content).strip().strip('"').strip("'")
    if not title:
        return

    session.title = title[:200]
    await db.commit()


async def compact_history(db: AsyncSession, session_id: UUID) -> None:
    """Background job body — folds everything but the most recent _COMPACTION_KEEP_RECENT
    messages into session.context_summary, merging with any prior summary, and advances
    summarized_through_message_id to the cutoff. Raw ChatMessage rows are never touched;
    this only shrinks what _build_history sends to the LLM on future turns. Safe to run
    more than once concurrently for the same session — worst case is redundant LLM work,
    not incorrect state, since each run does one read-then-write pass."""
    session = await db.get(ChatSession, session_id)
    if session is None:
        return

    rows = _unsummarized_rows(session, await get_session_messages(db, session.user_id, session_id))

    if len(rows) <= _COMPACTION_KEEP_RECENT:
        return

    to_summarize = rows[:-_COMPACTION_KEEP_RECENT]
    new_boundary = to_summarize[-1]

    transcript_text = "\n".join(f"{r.role.value}: {r.content}" for r in to_summarize if r.content)

    user = await db.get(User, session.user_id)
    if user is None:
        return

    try:
        provider = await get_provider(
            db, user.id, ProviderName(user.chat_provider.value), purpose="chat_compaction"
        )
        prompt = build_compaction_prompt(session.context_summary, transcript_text)
        response = await provider.get_chat_model().ainvoke([HumanMessage(content=prompt)])
    except Exception:  # noqa: BLE001 — a failed background compaction must never crash the job
        return

    await record_usage(
        db,
        user_id=user.id,
        session_id=session.id,
        provider=ProviderName(user.chat_provider.value),
        model=provider.model,
        operation="chat_compaction",
        usage=getattr(response, "usage_metadata", None),
    )

    summary = _stringify_content(response.content).strip()
    if not summary:
        return

    session.context_summary = summary
    session.summarized_through_message_id = new_boundary.id
    await db.commit()
