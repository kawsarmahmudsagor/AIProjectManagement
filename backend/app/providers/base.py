"""Common seam both AI providers implement (backend/DESIGN.md §4). Everything upstream
— extraction_service, the /ai/rewrite endpoint — talks to this Protocol only, never to
google-genai or openai directly, so swapping/adding a provider never touches call sites.
"""

from typing import Protocol

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from app.models.user import AgentPersona


class ConnectionStatus(BaseModel):
    ok: bool
    detail: str
    models: list[str] = []


class ExtractInput(BaseModel):
    """raw_bytes is populated for PDFs so the Gemini and OpenAI adapters can send the
    document directly (document vision handles multi-column layouts and scans far better
    than any local text extractor — see docs/RESEARCH.md §A4). extracted_text is always
    populated for docx/txt, and for pdf as the pre-flight/fallback input."""

    raw_bytes: bytes | None = None
    mime_type: str
    extracted_text: str | None = None
    filename: str


class BreakdownInput(BaseModel):
    """Same shape as ExtractInput plus `prompt` — a breakdown job may have a document, a
    free-text prompt, or both (BreakdownCreateRequest requires at least one), so every
    field here is optional and the adapter itself decides which content actually goes into
    the human message."""

    raw_bytes: bytes | None = None
    mime_type: str | None = None
    extracted_text: str | None = None
    filename: str | None = None
    prompt: str | None = None


class BragDocumentInput(BaseModel):
    """Grounding context for one Brag Document generation call — no PDF/document bytes,
    unlike ExtractInput/BreakdownInput, since the source file here is a spreadsheet
    parsed entirely by services/standup_excel_service.py before this ever reaches a
    provider. `work_log_entries` is the deterministic Excel parse (the primary source of
    truth); `projects`/`completed_tasks` are this same user's own saved DB rows, gathered
    the same way agents/chat_tools.py's project_search/task_search do but as plain
    function calls (see services/brag_document_service.py) — used only to add accurate
    terminology to a real logged task, never as a separate source of new facts."""

    member_name: str
    target_month: str
    work_log_entries: list[dict]
    projects: list[dict]
    completed_tasks: list[dict]


class ThumbnailPromptInput(BaseModel):
    """Grounding context for a project-thumbnail generation call — either a saved
    project's own fields, or (create-mode, per the product decision to auto-save first)
    the same shape built from the just-saved project. Plain strings only, no bytes: a
    thumbnail is generated from what the project *says* about itself, never from an
    uploaded document."""

    name: str
    role: str
    technologies: list[str] = []
    description_text: str = ""
    responsibilities_text: str = ""


class FAQPromptInput(BaseModel):
    """Grounding context for FAQ generation — same shape as ThumbnailPromptInput (a
    project's own name/role/technologies/description/responsibilities), kept as its own
    type rather than reused so the two features' input contracts can diverge
    independently later without a shared-type coupling."""

    name: str
    role: str
    technologies: list[str] = []
    description_text: str = ""
    responsibilities_text: str = ""


class GeneratedImage(BaseModel):
    """A raster image OR a rendered SVG poster — both flow through the same
    services/project_media_service.replace_media call, distinguished only by
    mime_type/generator. See services/thumbnail_service.py."""

    data: bytes
    mime_type: str


class ProviderError(Exception):
    """Raised by a provider adapter; extraction_service maps `code` onto the job's
    error_code / the frontend's error taxonomy (frontend/DESIGN.md §4.1)."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class LLMProvider(Protocol):
    async def extract(self, doc: ExtractInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        """Return a raw dict matching json_schema — callers validate against
        schemas.job.ExtractionResult themselves. `persona` selects which system prompt
        (Settings > AI Providers > Agent Persona) frames the extraction — see
        providers/prompts.py."""
        ...

    async def rewrite(
        self,
        *,
        op: str,
        target_text: str,
        source_text: str | None,
        char_limit: int | None,
        context: dict | None = None,
        instruction: str | None = None,
        persona: AgentPersona,
    ) -> str:
        """One of enhance-long / generate-short / enhance-short. `context` carries
        surrounding project fields (name, role, technologies) so the rewrite reads
        naturally next to the rest of the entry — see providers/prompts.py. `instruction`
        is a free-text ask the user typed for this one rewrite (e.g. "focus on the model
        training pipeline work"), taking priority over the default op instruction. Returns
        plain text (or a minimal HTML the caller wraps as <p>...</p>) — never raw markup
        from the model."""
        ...

    async def propose_breakdown(
        self, doc: BreakdownInput, json_schema: dict, *, persona: AgentPersona, max_tasks: int
    ) -> dict:
        """Return a raw dict matching json_schema (schemas.breakdown.LLMBreakdownResult) —
        services/breakdown_service.normalize_breakdown() repairs and validates it, so this
        method itself never needs to. Uses a higher max_output_tokens than extract() (a
        task tree is larger than 9 flat fields) — kept as its own constant per adapter
        rather than shared with extract(), so tuning one can't silently regress the other."""
        ...

    async def generate_brag_document(
        self, doc: BragDocumentInput, json_schema: dict, *, persona: AgentPersona
    ) -> dict:
        """Return a raw dict matching json_schema (schemas.brag_document.
        LLMBragDocumentResult) — services/brag_document_service.normalize_brag_document()
        repairs and validates it, so this method itself never needs to. Follows
        propose_breakdown's exact call shape (schema flattened via schema_utils.inline_refs,
        JSON-mode/response_schema, same error classification) since both are single-shot,
        larger-than-extraction structured-output calls."""
        ...

    async def generate_image(self, prompt: str, *, aspect_ratio: str = "16:9") -> GeneratedImage:
        """Text-to-image, for AI project thumbnails (services/thumbnail_service.py).
        Raises ProviderError("IMAGE_GENERATION_UNSUPPORTED", ...) when this provider has
        no image model configured/available (OpenAIProvider always does today) or when
        the configured model id itself isn't available for this account/tier — either
        way, that specific code is what thumbnail_service treats as "fall back to the
        deterministic SVG poster" rather than failing the job outright."""
        ...

    async def design_poster(
        self, ctx: ThumbnailPromptInput, json_schema: dict, *, persona: AgentPersona
    ) -> dict:
        """The SVG-poster fallback's text half: return a raw dict matching json_schema
        (schemas.thumbnail.LLMPosterSpec) — services/poster_renderer.normalize_poster_spec
        repairs and validates it, so this method itself never needs to. Same call shape as
        propose_breakdown (schema flattened via schema_utils.inline_refs, JSON-mode/
        response_schema, same error classification), since both are single-shot
        structured-output calls with no document input."""
        ...

    async def generate_faq(self, ctx: FAQPromptInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        """Return a raw dict matching json_schema (schemas.faq.LLMFAQResult) —
        services/faq_service.normalize_faq() repairs and validates it, so this method
        itself never needs to. Same call shape as design_poster/propose_breakdown (schema
        flattened via schema_utils.inline_refs, JSON-mode/response_schema, same error
        classification), since this is also a single-shot structured-output call with no
        document input."""
        ...

    async def test_connection(self) -> ConnectionStatus: ...

    @property
    def model(self) -> str:
        """The configured model name — lets a caller that only has an LLMProvider
        (e.g. chat_service tagging a usage_service.record_usage call) label usage rows
        without reaching into a private attribute."""
        ...

    def get_chat_model(self) -> BaseChatModel:
        """The underlying LangChain chat model, configured for open-ended conversation +
        tool-calling + streaming — no structured-output binding (that's extract()'s job).
        This is the one seam where agents/chatbot_graph.py reaches below the
        extract()/rewrite() abstraction to call .bind_tools()/.astream_events() directly."""
        ...
