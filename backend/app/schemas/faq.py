"""Schema for the "project fields -> curated FAQ" feature. LLMFAQResult doubles as both
the shape the provider is asked to fill AND the shape persisted on FAQJob.result once
services/faq_service.normalize_faq() has repaired it — no separate raw/clean type, same
convention as schemas/breakdown.py's LLMBreakdownResult.
"""

from pydantic import BaseModel, Field

MAX_FAQ_ITEMS = 6


class LLMFAQItem(BaseModel):
    question: str = ""
    answer: str = ""


class LLMFAQResult(BaseModel):
    items: list[LLMFAQItem] = Field(default_factory=list, max_length=MAX_FAQ_ITEMS)
