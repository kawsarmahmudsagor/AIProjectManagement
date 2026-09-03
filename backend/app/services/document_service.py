"""Upload handling: size/magic-byte validation and on-disk storage.

Files are written under a generated UUID name, never the client-supplied filename — the
original name is kept only as a DB column for display/download headers, closing the path
traversal hole a crafted filename (`../../etc/passwd`) would otherwise open
(backend/DESIGN.md §8).
"""

import hashlib
import uuid
from pathlib import Path
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.ingest.extract import XLSX_MIME_TYPE, UnsupportedFormatError, sniff_mime_type
from app.models.document import Document


class UploadTooLargeError(Exception):
    pass


async def save_upload(
    db: AsyncSession,
    settings: Settings,
    *,
    user_id: UUID,
    filename: str,
    data: bytes,
    project_id: UUID | None = None,
) -> Document:
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise UploadTooLargeError(f"File exceeds the {settings.max_upload_size_mb}MB limit")

    mime_type = sniff_mime_type(data, filename)  # raises UnsupportedFormatError for .doc etc.

    ext = {
        "application/pdf": ".pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "text/plain": ".txt",
        XLSX_MIME_TYPE: ".xlsx",
    }.get(mime_type, "")

    stored_name = f"{uuid.uuid4()}{ext}"
    user_dir = settings.uploads_dir / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    path: Path = user_dir / stored_name
    path.write_bytes(data)

    document = Document(
        user_id=user_id,
        project_id=project_id,
        filename=filename,
        storage_path=str(path),
        mime_type=mime_type,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


__all__ = ["save_upload", "UploadTooLargeError", "UnsupportedFormatError"]
