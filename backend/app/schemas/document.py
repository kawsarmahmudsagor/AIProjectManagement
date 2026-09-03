from uuid import UUID

from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: UUID
    # None when purpose="store_only" (the AI work-breakdown flow) — no ExtractionJob is
    # created in that case, so there's nothing to poll.
    job_id: UUID | None
