"""OpenAI provider, orchestrated through LangChain (`langchain-openai`) rather than
calling `openai` directly — same reasoning as the Gemini provider: this keeps the
provider layer composable with the rest of the LangChain-based orchestration (chains,
tracing, and Jarvis's tool-calling graph can all reuse the same `ChatOpenAI` instances).

We bind the raw `response_format` param via `.bind()` rather than depending on
`.with_structured_output()`'s internal method selection, for the same reason the other
two providers avoid it: it keeps the exact request shape explicit and stable across
`langchain-openai` versions.

`strict` is deliberately left off (defaults to `False`) on the json_schema response
format: OpenAI's strict mode requires every property to appear in the schema's
`required` array (optional fields must be modeled as nullable, never omitted), but the
schemas handed to `extract()` come from Pydantic models with default values (see
schemas/job.py's `LLMExtractedProject`) — Pydantic omits defaulted fields from
`required` entirely. Loosening to non-strict mode matches the guarantee level Gemini's
`response_schema` and Ollama's `format=` already provided (a strong hint, not a hard
constraint), rather than reshaping the schema just to satisfy strict mode.

PDFs are sent as a langchain-core standard multimodal "file" content block
(source_type="base64") — OpenAI's vision-capable models read them directly, unlike
Ollama which had no document-vision path at all.
"""

import base64
import json
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_provider_setting import ProviderName
from app.models.user import AgentPersona
from app.providers.base import (
    BragDocumentInput,
    BreakdownInput,
    ConnectionStatus,
    ExtractInput,
    FAQPromptInput,
    GeneratedImage,
    LLMProvider,
    ProviderError,
    ThumbnailPromptInput,
)
from app.providers.prompts import (
    BRAG_DOCUMENT_SYSTEM_PROMPTS,
    BREAKDOWN_SYSTEM_PROMPTS,
    EXTRACTION_SYSTEM_PROMPTS,
    FAQ_SYSTEM_PROMPTS,
    POSTER_DESIGN_SYSTEM_PROMPT,
    REWRITE_SYSTEM_PROMPTS,
    build_brag_document_prompt,
    build_breakdown_prompt,
    build_faq_prompt,
    build_poster_design_prompt,
    build_rewrite_prompt,
)
from app.services.usage_service import record_usage


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        *,
        db: AsyncSession | None = None,
        user_id: UUID | None = None,
        operation: str | None = None,
    ):
        self._api_key = api_key
        self._model_name = model
        # Present only when constructed via registry.get_provider — direct construction
        # (ai_settings.py's test_connection) leaves these None, and _log_usage below
        # no-ops in that case since test_connection never calls a logged method anyway.
        self._db = db
        self._user_id = user_id
        self._operation = operation

    @property
    def model(self) -> str:
        return self._model_name

    async def _log_usage(self, response: AIMessage) -> None:
        if self._db is None or self._user_id is None:
            return
        await record_usage(
            self._db,
            user_id=self._user_id,
            provider=ProviderName.OPENAI,
            model=self._model_name,
            operation=self._operation or "unknown",
            usage=getattr(response, "usage_metadata", None),
        )

    def _chat(self, *, temperature: float, max_tokens: int, response_format: dict | None = None):
        # A fresh instance per call — cheap wrappers, no persistent connection, keeps
        # this provider stateless like the other two.
        chat = ChatOpenAI(
            model=self._model_name, api_key=self._api_key, temperature=temperature, max_tokens=max_tokens
        )
        return chat.bind(response_format=response_format) if response_format else chat

    async def extract(self, doc: ExtractInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        if doc.raw_bytes and doc.mime_type == "application/pdf":
            human_content = [
                {
                    "type": "file",
                    "source_type": "base64",
                    "mime_type": doc.mime_type,
                    "data": base64.b64encode(doc.raw_bytes).decode(),
                    "filename": doc.filename,
                },
                {"type": "text", "text": "Extract the project into the given schema."},
            ]
        elif doc.extracted_text:
            human_content = [
                {"type": "text", "text": f"{doc.extracted_text}\n\nExtract the project into the given schema."}
            ]
        else:
            raise ProviderError("NO_TEXT_FOUND", "No extractable content in this document")

        chat = self._chat(
            temperature=0,
            max_tokens=8192,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "extraction_result", "schema": json_schema, "strict": False},
            },
        )

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=EXTRACTION_SYSTEM_PROMPTS[persona]), HumanMessage(content=human_content)]
            )
        except Exception as exc:  # langchain wraps provider errors inconsistently across versions
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "length":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "OpenAI hit the output token limit before finishing — the document may "
                "be too long, or contain more projects than expected.",
                retryable=True,
            )
        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)

        return json.loads(response.content)

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
        prompt = build_rewrite_prompt(op, source_text or target_text, char_limit, context, instruction)
        chat = self._chat(temperature=0.3, max_tokens=2048)

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=REWRITE_SYSTEM_PROMPTS[persona]), HumanMessage(content=prompt)]
            )
        except Exception as exc:
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)
        return str(response.content).strip()

    async def propose_breakdown(
        self, doc: BreakdownInput, json_schema: dict, *, persona: AgentPersona, max_tasks: int
    ) -> dict:
        human_content: list[dict] = []
        if doc.raw_bytes and doc.mime_type == "application/pdf":
            human_content.append(
                {
                    "type": "file",
                    "source_type": "base64",
                    "mime_type": doc.mime_type,
                    "data": base64.b64encode(doc.raw_bytes).decode(),
                    "filename": doc.filename or "document",
                }
            )
            human_content.append(
                {"type": "text", "text": build_breakdown_prompt(document_text=None, prompt=doc.prompt, max_tasks=max_tasks)}
            )
        else:
            human_content.append(
                {
                    "type": "text",
                    "text": build_breakdown_prompt(
                        document_text=doc.extracted_text, prompt=doc.prompt, max_tasks=max_tasks
                    ),
                }
            )

        # 16384, not extract()'s 8192 — see gemini.py's propose_breakdown for why.
        chat = self._chat(
            temperature=0,
            max_tokens=16384,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "breakdown_result", "schema": json_schema, "strict": False},
            },
        )

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=BREAKDOWN_SYSTEM_PROMPTS[persona]), HumanMessage(content=human_content)]
            )
        except Exception as exc:
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "length":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "The AI ran out of room before finishing — try again with fewer, larger tasks.",
                retryable=True,
            )
        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)

        return json.loads(response.content)

    async def generate_brag_document(
        self, doc: BragDocumentInput, json_schema: dict, *, persona: AgentPersona
    ) -> dict:
        human_content = [{"type": "text", "text": build_brag_document_prompt(doc)}]

        # 16384, not extract()'s 8192 — see gemini.py's generate_brag_document for why.
        chat = self._chat(
            temperature=0,
            max_tokens=16384,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "brag_document_result", "schema": json_schema, "strict": False},
            },
        )

        try:
            response = await chat.ainvoke(
                [
                    SystemMessage(content=BRAG_DOCUMENT_SYSTEM_PROMPTS[persona]),
                    HumanMessage(content=human_content),
                ]
            )
        except Exception as exc:
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "length":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "The AI ran out of room before finishing the brag document — try again.",
                retryable=True,
            )
        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)

        return json.loads(response.content)

    async def generate_image(self, prompt: str, *, aspect_ratio: str = "16:9") -> GeneratedImage:
        """OpenAI image generation is out of scope for this feature today — this always
        raises IMAGE_GENERATION_UNSUPPORTED, which services/thumbnail_service.py treats
        as "fall back to the deterministic SVG poster" rather than a hard failure. An
        OpenAI-configured user still gets a real generated thumbnail via design_poster
        below (a text-model call, which OpenAI does support), just not a raster image."""
        raise ProviderError(
            "IMAGE_GENERATION_UNSUPPORTED", "Image generation isn't available for the OpenAI provider yet."
        )

    async def design_poster(
        self, ctx: ThumbnailPromptInput, json_schema: dict, *, persona: AgentPersona
    ) -> dict:
        chat = self._chat(
            temperature=0.7,
            max_tokens=2048,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "poster_spec", "schema": json_schema, "strict": False},
            },
        )
        try:
            response = await chat.ainvoke(
                [
                    SystemMessage(content=POSTER_DESIGN_SYSTEM_PROMPT),
                    HumanMessage(content=build_poster_design_prompt(ctx)),
                ]
            )
        except Exception as exc:
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)
        return json.loads(response.content)

    async def generate_faq(self, ctx: FAQPromptInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        chat = self._chat(
            temperature=0.6,
            max_tokens=2048,
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "faq_result", "schema": json_schema, "strict": False},
            },
        )
        try:
            response = await chat.ainvoke(
                [SystemMessage(content=FAQ_SYSTEM_PROMPTS[persona]), HumanMessage(content=build_faq_prompt(ctx))]
            )
        except Exception as exc:
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        await self._log_usage(response)

        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "OpenAI returned no content", retryable=True)
        return json.loads(response.content)

    def get_chat_model(self) -> ChatOpenAI:
        # No response_format — chat is free text, not JSON-schema-constrained like extract().
        return ChatOpenAI(model=self._model_name, api_key=self._api_key, temperature=0.4, max_tokens=4096)

    async def test_connection(self) -> ConnectionStatus:
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)
            models = [m.id async for m in client.models.list()]
            return ConnectionStatus(ok=True, detail=f"OK — {len(models)} models available", models=models)
        except Exception as exc:  # noqa: BLE001
            code, _ = _classify_error(exc)
            if code == "PROVIDER_AUTH":
                return ConnectionStatus(
                    ok=False, detail="Invalid API key — create or check one at platform.openai.com/api-keys."
                )
            return ConnectionStatus(ok=False, detail=f"Unreachable: {exc}")


def _classify_error(exc: Exception) -> tuple[str, bool]:
    """LangChain doesn't normalize provider exceptions across integration versions, so we
    fall back to inspecting the underlying `openai` exception types when present, and the
    message otherwise (same approach as gemini.py's _classify_error)."""
    try:
        from openai import (
            APIConnectionError,
            APIStatusError,
            AuthenticationError,
            PermissionDeniedError,
            RateLimitError,
        )

        if isinstance(exc, RateLimitError):
            return "RATE_LIMITED", True
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            return "PROVIDER_AUTH", False
        if isinstance(exc, APIConnectionError):
            return "PROVIDER_UNREACHABLE", True
        if isinstance(exc, APIStatusError):
            if exc.status_code >= 500:
                return "PROVIDER_UNAVAILABLE", True
            return "PROVIDER_BAD_REQUEST", False
    except ImportError:
        pass

    message = str(exc).lower()
    if "429" in message or "rate limit" in message or "quota" in message:
        return "RATE_LIMITED", True
    if "401" in message or "403" in message or "api key" in message or "incorrect api key" in message:
        return "PROVIDER_AUTH", False
    return "PROVIDER_ERROR", False
