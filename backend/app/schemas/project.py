from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.schemas.common import RichText
from app.schemas.faq import LLMFAQItem
from app.schemas.project_media import ProjectMediaRef


class ProjectSection(BaseModel):
    """One long/short rich-text pair — used twice per project (description, responsibilities),
    mirroring the frontend's DualEditorField (frontend/DESIGN.md §3)."""

    long: RichText = RichText()
    short: RichText = RichText()


class ProjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=120)
    start_date: date
    end_date: date | None = None
    is_current: bool = False
    description: ProjectSection = ProjectSection()
    responsibilities: ProjectSection = ProjectSection()
    technologies: list[str] = Field(default_factory=list, max_length=40)
    project_url: str | None = None

    @field_validator("project_url")
    @classmethod
    def _validate_url(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        HttpUrl(v)  # raises if malformed
        return v

    @field_validator("description")
    @classmethod
    def _short_description_required(cls, v: ProjectSection) -> ProjectSection:
        if not v.short.text.strip():
            raise ValueError("Short summary is required")
        if len(v.short.text) > 390:
            raise ValueError("Description short summary must be 390 characters or fewer")
        if len(v.long.text) > 10_000:
            raise ValueError("Description long form must be 10,000 characters or fewer")
        return v

    @field_validator("responsibilities")
    @classmethod
    def _responsibilities_caps(cls, v: ProjectSection) -> ProjectSection:
        if len(v.short.text) > 390:
            raise ValueError("Responsibilities short summary must be 390 characters or fewer")
        if len(v.long.text) > 10_000:
            raise ValueError("Responsibilities long form must be 10,000 characters or fewer")
        return v

    @model_validator(mode="after")
    def _dates(self) -> "ProjectBase":
        if self.is_current:
            self.end_date = None
        elif self.end_date and self.end_date < self.start_date:
            raise ValueError("End date must be on or after the start date")
        return self


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    """All fields optional — PATCH semantics."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=120)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None
    description: ProjectSection | None = None
    responsibilities: ProjectSection | None = None
    technologies: list[str] | None = Field(default=None, max_length=40)
    project_url: str | None = None


class ProjectOut(ProjectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    # Populated by routers/projects.py's _to_out() from a separately-queried
    # ProjectMedia row (see services/project_media_service.py) — Project itself carries
    # no media columns, see models/project_media.py's docstring on why.
    thumbnail: ProjectMediaRef | None = None
    video: ProjectMediaRef | None = None
    # Populated by _to_out() from the latest succeeded FAQJob row (services/faq_service.
    # get_latest_result) — always a list, never None, so the frontend's only check is
    # "is it empty" (no separate "still generating" vs "nothing generated" state to
    # render; both look identical: no FAQ section). See faq_job.py's docstring for why
    # there is no Project.faq column.
    faq: list[LLMFAQItem] = []
    # Populated by _to_out() from services/video_frame_service.frames_by_project() —
    # stills extracted from the project's uploaded video, empty when there is no video or
    # extraction hasn't finished yet. See project_video_frame.py's docstring.
    video_frames: list[ProjectMediaRef] = []

    model_config = {"from_attributes": True}


class ProjectSummary(BaseModel):
    """Dashboard/list card payload — deliberately small. thumbnail_url is a bare string
    here rather than the full ProjectMediaRef: a list row only ever needs an <img src>
    and nothing else, and this list endpoint should not pay for a per-row nested object."""

    id: UUID
    name: str
    role: str
    start_date: date
    end_date: date | None
    is_current: bool
    short_summary_text: str
    technologies: list[str] = []
    thumbnail_url: str | None = None
    video_url: str | None = None

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
