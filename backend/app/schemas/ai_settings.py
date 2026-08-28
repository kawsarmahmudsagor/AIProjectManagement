from uuid import UUID

from pydantic import BaseModel

from app.models.ai_provider_setting import ProviderName


class ProviderSettingUpdate(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    is_default: bool | None = None


class ProviderSettingOut(BaseModel):
    id: UUID
    provider: ProviderName
    api_key_masked: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    is_default: bool

    model_config = {"from_attributes": True}


class ConnectionTestResult(BaseModel):
    ok: bool
    detail: str
    models: list[str] = []


class ProviderModelCatalog(BaseModel):
    models: list[str]
    default: str


class RewriteContext(BaseModel):
    """Surrounding project fields sent alongside the box's own text so the rewrite is
    grounded in the rest of the entry — e.g. "Enhance with AI" on the Responsibilities
    box should read naturally next to the project's name/role/technologies, not be
    generated in a vacuum. All optional: the box's own text is always sufficient to
    generate something, context only improves coherence with the rest of the form."""

    project_name: str | None = None
    role: str | None = None
    technologies: list[str] = []


class RewriteRequest(BaseModel):
    op: str  # "enhance-long" | "generate-short" | "enhance-short"
    section: str  # "description" | "responsibilities"
    target_html: str = ""
    source_html: str = ""
    context: RewriteContext | None = None
    instruction: str | None = None
    provider: ProviderName | None = None


class RewriteResponse(BaseModel):
    html: str
    text: str
