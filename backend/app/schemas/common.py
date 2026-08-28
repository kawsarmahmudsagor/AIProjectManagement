"""RichText mirrors the frontend's `type RichText = { html: string; text: string }`
(frontend/DESIGN.md §1a). `text` is advisory from the client — services always recompute
it server-side from `html` before persisting or validating length caps against it.
"""

from pydantic import BaseModel, Field


class RichText(BaseModel):
    html: str = ""
    text: str = ""


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ErrorDetail(BaseModel):
    code: str
    message: str
    # Which provider produced this error, e.g. "gemini" — lets the frontend show a
    # provider-specific message (API key expired / limit reached) without re-deriving it.
    provider: str | None = None
