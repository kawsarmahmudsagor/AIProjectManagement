import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.chat import ChatRole
from app.models.user import ChatProvider


class ChatMessageIn(BaseModel):
    content: str
    provider: ChatProvider | None = None  # per-request override of users.chat_provider


class ChatMessageOut(BaseModel):
    id: UUID
    role: ChatRole
    content: str
    tool_calls: list[dict] | None = None
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_result: dict | None = None
    created_at: datetime

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
