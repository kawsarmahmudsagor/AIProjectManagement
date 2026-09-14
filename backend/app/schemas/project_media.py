from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import ErrorDetail


class ProjectMediaRef(BaseModel):
    """A media pointer as the frontend consumes it — a relative URL string, not an id,
    not a base64 payload, following the same convention as
    schemas.profile.PhotoUploadResponse.photo_url. `url` carries a `?v=<sha prefix>`
    cache-buster because the path itself is stable across replaces; without it a
    replaced thumbnail keeps showing the old image until a hard reload."""

    url: str
    mime_type: str
    size_bytes: int
    origin: Literal["uploaded", "generated"]
    generator: str | None = None


class ThumbnailGenerationContext(BaseModel):
    """Sent by the frontend when a project isn't saved yet (the "Add New Project" page
    auto-saves before generating per the product decision, but this schema also lets the
    client pass its own in-form values so the check and the call can share one shape
    regardless of when it runs)."""

    name: str | None = None
    role: str | None = None
    technologies: list[str] = []
    description_text: str | None = None
    responsibilities_text: str | None = None


class ThumbnailGenerateRequest(BaseModel):
    context: ThumbnailGenerationContext = ThumbnailGenerationContext()


class ThumbnailGenerateResponse(BaseModel):
    job_id: UUID


class ThumbnailJobOut(BaseModel):
    id: UUID
    status: str
    result: ProjectMediaRef | None = None
    error: ErrorDetail | None = None
