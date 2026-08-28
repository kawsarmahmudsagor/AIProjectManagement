from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.schemas.common import RichText


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

    model_config = {"from_attributes": True}


class ProjectSummary(BaseModel):
    """Dashboard card payload — deliberately small."""

    id: UUID
    name: str
    role: str
    start_date: date
    end_date: date | None
    is_current: bool
    short_summary_text: str

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    items: list[ProjectSummary]
    total: int
