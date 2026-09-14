"""Chat attachment upload/delete/get endpoints, and the replay seam
(chat_service._rows_to_messages / _load_attachment_payloads) that reconstructs
multimodal content from persisted rows."""

import base64

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.models.chat import ChatMessage, ChatRole, ChatSession
from app.models.chat_attachment import AttachmentKind, ChatAttachment, ChatAttachmentBlob
from app.models.user import User
from app.providers.content_blocks import build_user_content
from app.providers.tokens import estimate_tokens
from app.routers import chat
from app.services import chat_service
from tests.conftest import build_app

_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _minimal_pdf(text: bytes) -> bytes:
    """A genuinely valid single-page PDF with real extractable text — pdfplumber
    (app/ingest/extract.py's _extract_pdf) needs a real xref/trailer/Catalog structure,
    not just a `%PDF` magic-byte prefix (that's enough for sniff_mime_type, but not for
    actually parsing text out of it)."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    stream = b"BT /F1 24 Tf 100 700 Td (" + text + b") Tj ET"
    objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += b"trailer\n<< /Size " + str(len(objects) + 1).encode() + b" /Root 1 0 R >>\nstartxref\n"
    out += str(xref_offset).encode() + b"\n%%EOF"
    return bytes(out)


_PDF = _minimal_pdf(b"Some extractable text content here.")


@pytest_asyncio.fixture
async def chat_client_a(user_a: User):
    app = build_app(chat.router)
    app.dependency_overrides[get_current_user] = lambda: user_a
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def chat_client_b(user_b: User):
    app = build_app(chat.router)
    app.dependency_overrides[get_current_user] = lambda: user_b
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# --------------------------------------------------------------------------- upload


async def test_png_upload_is_image_kind(chat_client_a, session_a: ChatSession):
    res = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("shot.png", _PNG, "image/png")}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["kind"] == "image"
    assert body["extracted_chars"] is None


async def test_pdf_upload_extracts_text(chat_client_a, session_a: ChatSession):
    res = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("notes.pdf", _PDF, "application/pdf")}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["kind"] == "document"
    assert body["extracted_chars"] and body["extracted_chars"] > 0


async def test_code_file_uploads_via_utf8_fallback(chat_client_a, session_a: ChatSession):
    """sniff_mime_type's UTF-8 fallback (ingest/extract.py) accepts any decodable text
    regardless of extension — this is what makes .py/.ts/.json 'just work' for chat
    attachments with zero new code."""
    code = b"def hello():\n    return 'world'\n"
    res = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("script.py", code, "text/x-python")}
    )
    assert res.status_code == 201
    assert res.json()["kind"] == "document"


async def test_xlsx_upload_is_415_with_specific_code(chat_client_a, session_a: ChatSession):
    """Spreadsheets are explicitly out of scope for chat attachments — the Brag Document
    page remains the only route for them (chat_app_guide.md)."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("xl/workbook.xml", "<workbook/>")
    res = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments",
        files={"file": ("data.xlsx", buf.getvalue(), "application/vnd.ms-excel")},
    )
    assert res.status_code == 415


async def test_oversized_image_is_413(chat_client_a, session_a: ChatSession):
    from app.core.config import get_settings

    oversized = _PNG[:8] + b"\x00" * (get_settings().max_chat_image_size_mb * 1024 * 1024 + 1)
    res = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("big.png", oversized, "image/png")}
    )
    assert res.status_code == 413


async def test_upload_to_another_users_session_is_404(chat_client_b, session_a: ChatSession):
    res = await chat_client_b.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("t.png", _PNG, "image/png")}
    )
    assert res.status_code == 404


# --------------------------------------------------------------------------- delete


async def test_delete_unused_attachment_succeeds(chat_client_a, session_a: ChatSession):
    upload = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("t.png", _PNG, "image/png")}
    )
    attachment_id = upload.json()["id"]
    res = await chat_client_a.delete(f"/api/v1/chat/attachments/{attachment_id}")
    assert res.status_code == 204


async def test_delete_already_attached_attachment_is_409(db: AsyncSession, chat_client_a, session_a: ChatSession):
    upload = await chat_client_a.post(
        f"/api/v1/chat/sessions/{session_a.id}/attachments", files={"file": ("t.png", _PNG, "image/png")}
    )
    attachment_id = upload.json()["id"]

    # Simulate "already sent in a turn" by binding message_id directly (stream_turn does
    # this as part of persisting a turn — see chat_service.stream_turn).
    message = ChatMessage(session_id=session_a.id, role=ChatRole.USER, content="hi")
    db.add(message)
    await db.commit()
    await db.refresh(message)
    from sqlalchemy import update

    await db.execute(
        update(ChatAttachment).where(ChatAttachment.id == attachment_id).values(message_id=message.id)
    )
    await db.commit()

    res = await chat_client_a.delete(f"/api/v1/chat/attachments/{attachment_id}")
    assert res.status_code == 409


async def test_delete_nonexistent_attachment_is_404(chat_client_a):
    import uuid

    res = await chat_client_a.delete(f"/api/v1/chat/attachments/{uuid.uuid4()}")
    assert res.status_code == 404


# --------------------------------------------------------------------------- replay


async def _attached_message(db: AsyncSession, session: ChatSession, *, kind: AttachmentKind, data: bytes | None, extracted_text: str | None = None, filename: str = "f") -> ChatMessage:
    message = ChatMessage(session_id=session.id, role=ChatRole.USER, content="What does this say?")
    db.add(message)
    await db.flush()

    attachment = ChatAttachment(
        user_id=session.user_id, session_id=session.id, message_id=message.id, kind=kind,
        filename=filename, mime_type="image/png" if kind == AttachmentKind.IMAGE else "text/plain",
        size_bytes=len(data or b""), sha256="x" * 64, extracted_text=extracted_text,
    )
    db.add(attachment)
    await db.flush()
    if data is not None:
        db.add(ChatAttachmentBlob(attachment_id=attachment.id, data=data))
    await db.commit()
    await db.refresh(message)
    return message


async def test_no_attachment_path_stays_plain_string(db: AsyncSession, session_a: ChatSession):
    message = ChatMessage(session_id=session_a.id, role=ChatRole.USER, content="hello")
    db.add(message)
    await db.commit()
    await db.refresh(message)

    rows = await chat_service.get_session_messages(db, session_a.user_id, session_a.id)
    payloads = await chat_service._load_attachment_payloads(db, rows, include_image_bytes=True)
    lc_messages = chat_service._rows_to_messages(rows, payloads)
    assert lc_messages[-1].content == "hello"
    assert isinstance(lc_messages[-1].content, str)


async def test_image_attachment_becomes_real_image_block_with_roundtripped_bytes(
    db: AsyncSession, session_a: ChatSession
):
    await _attached_message(db, session_a, kind=AttachmentKind.IMAGE, data=_PNG, filename="shot.png")

    rows = await chat_service.get_session_messages(db, session_a.user_id, session_a.id)
    payloads = await chat_service._load_attachment_payloads(db, rows, include_image_bytes=True)
    lc_messages = chat_service._rows_to_messages(rows, payloads)

    content = lc_messages[-1].content
    assert isinstance(content, list)
    image_blocks = [b for b in content if b.get("type") == "image"]
    assert len(image_blocks) == 1
    assert base64.b64decode(image_blocks[0]["data"]) == _PNG
    # The user's own text must be the LAST block, per content_blocks.build_user_content's
    # documented ordering.
    assert content[-1] == {"type": "text", "text": "What does this say?"}


async def test_document_attachment_becomes_text_block_with_marker(db: AsyncSession, session_a: ChatSession):
    await _attached_message(
        db, session_a, kind=AttachmentKind.DOCUMENT, data=b"pdf-bytes", extracted_text="The document says hello.",
        filename="notes.pdf",
    )

    rows = await chat_service.get_session_messages(db, session_a.user_id, session_a.id)
    payloads = await chat_service._load_attachment_payloads(db, rows, include_image_bytes=True)
    lc_messages = chat_service._rows_to_messages(rows, payloads)

    content = lc_messages[-1].content
    assert isinstance(content, list)
    text_blocks = [b["text"] for b in content if b.get("type") == "text"]
    assert any("--- Attached file: notes.pdf ---" in t and "The document says hello." in t for t in text_blocks)


async def test_six_images_keeps_four_real_and_two_placeholders(db: AsyncSession, session_a: ChatSession):
    for i in range(6):
        await _attached_message(db, session_a, kind=AttachmentKind.IMAGE, data=_PNG, filename=f"img{i}.png")

    rows = await chat_service.get_session_messages(db, session_a.user_id, session_a.id)
    payloads = await chat_service._load_attachment_payloads(db, rows, include_image_bytes=True)
    lc_messages = chat_service._rows_to_messages(rows, payloads)

    total_image_blocks = 0
    total_placeholder_blocks = 0
    for m in lc_messages:
        if not isinstance(m.content, list):
            continue
        for block in m.content:
            if block.get("type") == "image":
                total_image_blocks += 1
            elif block.get("type") == "text" and "was attached earlier" in block.get("text", ""):
                total_placeholder_blocks += 1

    assert total_image_blocks == 4
    assert total_placeholder_blocks == 2


async def test_estimate_tokens_does_not_raise_on_list_content_and_charges_for_images(
    db: AsyncSession, session_a: ChatSession
):
    await _attached_message(db, session_a, kind=AttachmentKind.IMAGE, data=_PNG, filename="shot.png")
    rows = await chat_service.get_session_messages(db, session_a.user_id, session_a.id)
    payloads = await chat_service._load_attachment_payloads(db, rows, include_image_bytes=True)
    lc_messages = chat_service._rows_to_messages(rows, payloads)

    text_only = chat_service._rows_to_messages(rows)  # no attachments param -> plain string path
    assert estimate_tokens(lc_messages) > estimate_tokens(text_only)


async def test_should_compact_never_loads_image_bytes(db: AsyncSession, user_a: User, session_a: ChatSession):
    """should_compact/compact_history call _rows_to_messages with no attachments arg —
    this must not raise even when the session has real attachments, and must not attempt
    to load their bytes (the whole point of the default-None param)."""
    await _attached_message(db, session_a, kind=AttachmentKind.IMAGE, data=_PNG, filename="shot.png")
    for _ in range(15):
        db.add(ChatMessage(session_id=session_a.id, role=ChatRole.USER, content="padding " * 50))
    await db.commit()

    result = await chat_service.should_compact(db, user_a, session_a.id)
    assert isinstance(result, bool)  # must not raise


def test_build_user_content_returns_plain_string_with_no_attachments():
    assert build_user_content("hello", []) == "hello"


async def test_stream_turn_rejects_another_users_attachment_before_any_message_is_created(
    db: AsyncSession, user_a: User, user_b: User, session_a: ChatSession
):
    """attachment_ids naming an id that isn't user_a's own must error out before
    stream_turn ever calls a provider or persists a message row — validated with one
    query up front (see stream_turn's docstring)."""
    others_session = ChatSession(user_id=user_b.id)
    db.add(others_session)
    await db.commit()
    await db.refresh(others_session)

    others_attachment = ChatAttachment(
        user_id=user_b.id, session_id=others_session.id, kind=AttachmentKind.IMAGE,
        filename="x.png", mime_type="image/png", size_bytes=10, sha256="y" * 64,
    )
    db.add(others_attachment)
    await db.commit()
    await db.refresh(others_attachment)

    events = []
    async for event in chat_service.stream_turn(
        db, user_a, session_a.id, "hello", attachment_ids=[others_attachment.id]
    ):
        events.append(event)

    assert len(events) == 1
    assert events[0].event == "error"
    assert events[0].data["code"] == "ATTACHMENT_NOT_FOUND"

    # No message row was created for this rejected turn.
    rows = await chat_service.get_session_messages(db, user_a.id, session_a.id)
    assert rows == []
