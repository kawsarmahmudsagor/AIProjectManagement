"""Schemas for the Brag Document Generator feature.

LLMTechnicalContributionGroup/LLMBragDocumentResult double as both the shape the provider
is asked to fill AND the shape persisted on BragDocumentJob.result once
normalize_brag_document() has repaired it — same "no separate raw vs. clean type" pattern
as schemas/breakdown.py's LLMBreakdownResult. Deliberately flat and hour/date-free: no
field here carries an hour count or a date, because every deterministic number belongs on
HourStatsOut/BragDocumentJob.hour_stats instead — see brag_document_job.py's docstring.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.ai_provider_setting import ProviderName


class LLMBulletGroup(BaseModel):
    """One named technical theme within a project (e.g. "RAG Implementation"), used when
    a project's logged work is detailed enough to split into more than one theme — see
    LLMTechnicalContributionGroup.subsections."""

    heading: str = ""
    bullets: list[str] = Field(default_factory=list, max_length=30)


class LLMTechnicalContributionGroup(BaseModel):
    """One project/initiative's worth of technical work. `project_name` is either an
    exact match against one of the user's saved Project names, or — just as often — a
    name/title for a real initiative identified directly from the work log that isn't one
    of the user's saved Projects (see providers/prompts.py's BRAG_DOCUMENT_SYSTEM_PROMPTS
    on why "On Demand / Miscellaneous" is a last resort, not a default, for unmatched
    work). `subsections` groups bullets under named sub-themes for a project detailed
    enough to warrant it (e.g. "MLOps & Fine-Tuning Pipeline", "RAG Implementation");
    `bullets` is the flat fallback for a project that doesn't split into distinct themes —
    a group normally has content in exactly one of the two, never a meaningful mix.
    `key_contribution` is a short synthesis paragraph of this project's value/impact for
    the month, still grounded in the bullets above it."""

    project_name: str = ""
    bullets: list[str] = Field(default_factory=list, max_length=30)
    subsections: list[LLMBulletGroup] = Field(default_factory=list, max_length=10)
    key_contribution: str = ""


class LLMImpactArea(BaseModel):
    """One discipline/area (e.g. "MLOps", "RAG", "Voice AI") the month's work touched,
    with a one-sentence summary — see LLMBragDocumentResult.overall_impact."""

    category: str = ""
    summary: str = ""


class LLMBragDocumentResult(BaseModel):
    technical_contributions: list[LLMTechnicalContributionGroup] = Field(default_factory=list, max_length=30)
    team_support_bullets: list[str] = Field(default_factory=list, max_length=30)
    learning_bullets: list[str] = Field(default_factory=list, max_length=30)
    overall_impact: list[LLMImpactArea] = Field(default_factory=list, max_length=10)
    confidence_notes: list[str] = Field(default_factory=list, max_length=10)


class HourStatsOut(BaseModel):
    """Mirrors services/standup_excel_service.py's MemberMonthlySummary 1:1 — every field
    here is deterministic arithmetic computed by aggregate_member_month(), never
    LLM-authored. The subtitle line (period/hours/sprints) on both the export renderer and
    the frontend result view is built from this object only, never from `result`."""

    member_name: str
    month_name: str
    year: int
    included_weeks: list[str]
    total_hours: float
    expected_target_hours: float
    gross_base_hours: float
    holiday_deducted_hours: float
    holiday_count: int
    holiday_names: list[str]
    leave_count: int
    leave_hours: float
    leave_dates: list[str]
    blocker_count: int
    billable_hours: float
    non_billable_hours: float
    balance_hours: float
    target_completion_pct: float


class BragDocumentPreviewResponse(BaseModel):
    """Response for POST /brag-documents/preview — a synchronous parse, no job row yet.
    `detected_member_name` is None when the auto-match confidence fell below
    standup_excel_service.MEMBER_MATCH_CONFIDENCE_THRESHOLD, in which case the frontend
    must fall back to a manual dropdown built from `candidate_member_names`."""

    document_id: UUID
    detected_member_name: str | None
    match_confidence: float
    candidate_member_names: list[str]
    available_months: list[str]


class BragDocumentCreateRequest(BaseModel):
    document_id: UUID
    member_name: str = Field(min_length=1, max_length=200)
    target_month: str = Field(min_length=1, max_length=20)
    provider: ProviderName | None = None
    # Optional override — omit to default to f"{target_month} Brag Document" (see
    # models/brag_document_job.py's docstring on the `name` column).
    name: str | None = Field(default=None, max_length=255)


class BragDocumentJobCreated(BaseModel):
    id: UUID


class BragDocumentJobSummary(BaseModel):
    """One row in the saved-documents list (GET /brag-document-jobs) — lighter than
    BragDocumentJobOut since a list view has no use for the full drafted prose/hour
    breakdown, only enough to identify and open one entry."""

    id: UUID
    name: str
    status: str
    member_name: str
    target_month: str
    created_at: datetime


class BragDocumentJobListResponse(BaseModel):
    items: list[BragDocumentJobSummary]
    total: int


class BragDocumentJobOut(BaseModel):
    id: UUID
    name: str
    status: str
    document_id: UUID
    member_name: str
    target_month: str
    # Always the *effective* content (the user's saved edit once one exists, else the
    # original LLM draft) — see BragDocumentJob.effective_result. The frontend never
    # sees the raw/edited split; `is_edited` is only so it knows whether to offer
    # "Reset changes".
    result: LLMBragDocumentResult | None
    is_edited: bool
    hour_stats: HourStatsOut | None
    error_code: str | None
    error_message: str | None
