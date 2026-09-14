import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDPk


class AttachmentKind(StrEnum):
    IMAGE = "image"  # goes to the model as a true multimodal content block
    DOCUMENT = "document"  # extracted to text at upload and injected as context


attachment_kind_enum = Enum(AttachmentKind, name="attachment_kind")


class ChatAttachment(Base, UUIDPk):
    """A file attached to one chat message. Created by POST /chat/sessions/{id}/
    attachments *before* the message it belongs to exists (message_id is NULL until the
    turn is sent), which is the main reason this is a table and not a JSONB column on
    chat_messages — see the plan's Part 5 and providers/content_blocks.py.

    extracted_text is populated at upload time for kind=DOCUMENT by ingest/extract.ingest
    (so a large PDF is parsed once, inside a request that can still return a clean
    415/413, rather than mid-SSE-stream where routers/chat.py can only emit an `error`
    event after the response has already committed to 200). For kind=IMAGE it stays NULL
    and the bytes are what gets replayed.
    """

    __tablename__ = "chat_attachments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # SET NULL, not CASCADE: chat_sessions cascade-deletes chat_messages, and this row is
    # deleted by its own session_id cascade anyway — SET NULL avoids depending on cascade
    # ordering between two paths to the same row (same call as
    # chat_sessions.summarized_through_message_id, models/chat.py).
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    kind: Mapped[AttachmentKind] = mapped_column(attachment_kind_enum, nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # True when extracted_text was cut at _MAX_ATTACHMENT_TEXT_CHARS — surfaced in the
    # injected context so the model knows it's seeing a prefix, and in ChatAttachmentOut
    # so the UI can say so too.
    text_truncated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["ChatMessage | None"] = relationship(  # noqa: F821
        back_populates="attachments", foreign_keys=[message_id]
    )


class ChatAttachmentBlob(Base):
    """Same metadata/bytes split as ProjectMediaBlob, same no-relationship rule — bytes
    are reached only via an explicit select in services/chat_service.py."""

    __tablename__ = "chat_attachment_blobs"

    attachment_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("chat_attachments.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
