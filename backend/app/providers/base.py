"""Common seam both AI providers implement (backend/DESIGN.md §4). Everything upstream
— extraction_service, the /ai/rewrite endpoint — talks to this Protocol only, never to
google-genai or ollama directly, so swapping/adding a provider never touches call sites.
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
    """raw_bytes is populated for PDFs so the Gemini adapter can send the document
    directly (document vision handles multi-column layouts and scans far better than any
    local text extractor — see docs/RESEARCH.md §A4). extracted_text is always populated
    for docx/txt, and for pdf as the pre-flight/fallback and the only input Ollama can use
    (it has no document-vision path)."""

    raw_bytes: bytes | None = None
    mime_type: str
    extracted_text: str | None = None
    filename: str


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

    async def test_connection(self) -> ConnectionStatus: ...

    def get_chat_model(self) -> BaseChatModel:
        """The underlying LangChain chat model, configured for open-ended conversation +
        tool-calling + streaming — no structured-output binding (that's extract()'s job).
        This is the one seam where agents/chatbot_graph.py reaches below the
        extract()/rewrite() abstraction to call .bind_tools()/.astream_events() directly."""
        ...
