import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.chat import ChatRole
from app.models.chat_attachment import AttachmentKind
from app.models.user import ChatProvider


class ChatMessageIn(BaseModel):
    content: str
    provider: ChatProvider | None = None  # per-request override of users.chat_provider
    # Ids from POST /chat/sessions/{id}/attachments — never raw bytes, so retrying an
    # aborted SSE stream re-sends ~100 bytes of JSON instead of re-uploading every file.
    # Capped at 5: each one is replayed into every subsequent turn's context too.
    attachment_ids: list[UUID] = Field(default_factory=list, max_length=5)


class ChatAttachmentOut(BaseModel):
    id: UUID
    filename: str
    mime_type: str
    size_bytes: int
    kind: AttachmentKind
    # Bare backend path (no /api/v1 prefix) — resolved through the frontend's BFF, same
    # convention as schemas.project_media.ProjectMediaRef.
    url: str
    extracted_chars: int | None = None
    text_truncated: bool = False


class ChatMessageOut(BaseModel):
    id: UUID
    role: ChatRole
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_result: dict | None = None
    created_at: datetime
    attachments: list[ChatAttachmentOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: UUID
    title: str
    last_message_at: datetime
    starred: bool

    model_config = {"from_attributes": True}


class ChatSessionListResponse(BaseModel):
    items: list[ChatSessionOut]
    total: int


class ChatSessionStarUpdate(BaseModel):
    starred: bool


@dataclass
class ChatSSEEvent:
    """The one place the `event: <name>\\ndata: <json>\\n\\n` SSE wire format is defined —
    see backend/DESIGN.md-equivalent plan §B.6 for the canonical event/data contract:
    session_meta, token, tool_start, tool_end, done, error.
    """

    event: str
    data: dict = field(default_factory=dict)

    def to_sse(self) -> str:
        return f"event: {self.event}\ndata: {json.dumps(self.data)}\n\n"
