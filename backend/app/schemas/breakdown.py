"""Schemas for the "document -> AI work breakdown" flagship feature (backend/DESIGN.md
§8). LLMProposedTask/LLMBreakdownResult double as both the shape the provider is asked to
fill AND the shape persisted on BreakdownJob.result once normalize_breakdown() has
repaired it — there is no separate "raw" vs "clean" type, because normalization mutates
fields in place rather than reshaping them.

Deliberately flat: a recursive `subtasks: list[LLMProposedTask]` field is not merely
risky, it is an import-time RecursionError the moment `inline_refs()` (schema_utils.py)
tries to flatten it — see that module's docstring. `parent_ref` (a named handle) plus
"depth capped at 1, enforced in Python" is what buys the two-level tree this feature needs
without a recursive schema.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.ai_provider_setting import ProviderName
from app.schemas.task import TaskOut

EstimateSize = Literal["xs", "s", "m", "l", "xl"]
BreakdownPriority = Literal["low", "medium", "high", "urgent"]


class LLMProposedTask(BaseModel):
    """One proposed task. `ref` is a named handle (e.g. "t1"), not a positional index —
    self-checking, unlike `parent_index: int`, where an off-by-one is silent and a task
    nests under the wrong parent while still looking entirely plausible.

    `grounded` + `source_quote` is the provenance obligation that makes this feature
    honest (see providers/prompts.py's BREAKDOWN_SYSTEM_PROMPTS docstring): a task claimed
    grounded must carry a verbatim quote proving it, and normalize_breakdown() demotes any
    grounded=true item with no quote rather than trusting the flag alone.
    """

    ref: str = ""
    title: str = ""
    description: str = ""
    grounded: bool = False
    phase: str | None = None
    parent_ref: str | None = None
    priority: BreakdownPriority = "medium"
    estimate_size: EstimateSize | None = None
    source_quote: str | None = None


class LLMBreakdownResult(BaseModel):
    tasks: list[LLMProposedTask] = Field(default_factory=list, max_length=60)
    confidence_notes: list[str] = Field(default_factory=list, max_length=10)


class BreakdownCreateRequest(BaseModel):
    """Exactly one source of content is required: an already-uploaded document, or a
    free-text prompt describing the work (the "just describe it" launcher option) — never
    neither, and both together is allowed (a document plus extra instructions)."""

    document_id: UUID | None = None
    prompt: str | None = Field(default=None, max_length=4000)
    provider: ProviderName | None = None
    max_tasks: int = Field(default=25, ge=1, le=60)

    @model_validator(mode="after")
    def _require_a_source(self) -> "BreakdownCreateRequest":
        if self.document_id is None and not (self.prompt or "").strip():
            raise ValueError("Provide a document, a prompt, or both")
        return self


class BreakdownJobCreated(BaseModel):
    id: UUID


class BreakdownJobOut(BaseModel):
    id: UUID
    status: str
    document_id: UUID | None
    prompt: str | None
    max_tasks: int
    is_scanned: bool
    result: LLMBreakdownResult | None
    # ref -> id of the Task actually created for it. A dict, not the bare list the initial
    # design sketched, because /accept must be resumable across multiple partial-accept
    # calls (backend/DESIGN.md §8's "unaccepted rows stay editable for a second pass") and
    # needs somewhere to resolve a later batch's parent_ref against an earlier batch's
    # already-created task.
    accepted: dict[str, UUID]
    dismissed_refs: list[str]
    error_code: str | None
    error_message: str | None


class BreakdownAcceptItem(BaseModel):
    """What the review UI sends back for one task the user chose to keep — the user's
    edited values, not a bare ref, since title/description/priority/hours are all
    editable in the review row before acceptance. `parent_ref` is resolved against other
    items in the same request first, then against BreakdownJob.accepted_refs from an
    earlier partial accept; if it resolves to neither, the service promotes the item to
    top-level rather than rejecting the whole request."""

    ref: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    priority: BreakdownPriority = "medium"
    # The review row prefills its editable hours input from estimate_size via the same
    # BREAKDOWN_ESTIMATE_SIZE_MINUTES table the backend uses (core/config.py) — sending
    # estimate_size along too lets the backend re-derive the default itself rather than
    # trusting the frontend's copy of that table as the only source of truth.
    estimate_minutes: int | None = Field(default=None, ge=1, le=100_000)
    estimate_size: EstimateSize | None = None
    phase: str | None = None
    parent_ref: str | None = None


class BreakdownAcceptRequest(BaseModel):
    items: list[BreakdownAcceptItem] = Field(min_length=1, max_length=60)
    dry_run: bool = False


class BreakdownSkippedItem(BaseModel):
    ref: str
    reason: str


class BreakdownAcceptResponse(BaseModel):
    created: list[TaskOut]
    skipped: list[BreakdownSkippedItem]
    # Refs that were selected as a subtask but whose parent wasn't selected/resolvable —
    # created as top-level tasks instead of silently dropped or silently auto-including
    # their parent (backend/DESIGN.md §8's promotion-warning rule).
    promoted_refs: list[str]


class BreakdownDismissRequest(BaseModel):
    refs: list[str] = Field(min_length=1, max_length=100)
