from uuid import UUID

from pydantic import BaseModel

from app.models.extraction_job import JobStatus
from app.schemas.common import ErrorDetail
from app.schemas.project import ProjectSection


class ExtractedProject(BaseModel):
    """A subset of ProjectCreate's fields — the shape persisted on the job and handed to
    the frontend. Dates come back as ISO strings-or-null since the model may not find
    them; never invent a value here (see DESIGN.md §4 prompt design notes)."""

    name: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: ProjectSection = ProjectSection()
    responsibilities: ProjectSection = ProjectSection()
    technologies: list[str] = []


class ExtractionResult(BaseModel):
    project: ExtractedProject
    confidence_notes: list[str] = []


class LLMExtractedProject(BaseModel):
    """What the LLM provider is actually asked to fill. Deliberately flat, plain-text-only
    fields for description/responsibilities — mirroring ai_service.rewrite_field and
    project_service._apply_section, the LLM never authors a RichText's html/text pair
    itself, extraction_service derives both deterministically from this. This also halves
    the free-text tokens the model must produce for these two fields versus asking for a
    nested {long:{html,text}, short:{html,text}} object, which measurably reduced silent
    truncation of exactly these fields under the output token cap."""

    name: str | None = None
    role: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description_long: str | None = None
    description_short: str | None = None
    responsibilities_long: str | None = None
    responsibilities_short: str | None = None
    technologies: list[str] = []


class LLMExtractionResult(BaseModel):
    project: LLMExtractedProject
    confidence_notes: list[str] = []


class JobStatusOut(BaseModel):
    id: UUID
    status: JobStatus
    result: ExtractionResult | None = None
    error: ErrorDetail | None = None
