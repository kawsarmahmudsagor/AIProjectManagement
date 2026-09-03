"""Gemini provider, orchestrated through LangChain (`langchain-google-genai`) rather than
calling `google-genai` directly — this keeps the provider layer composable with the rest
of the LangChain-based orchestration (chains, tracing, and the planned chatbot feature can
reuse the same `ChatGoogleGenerativeAI` instances). We still bind the raw structured-output
config ourselves instead of relying on `.with_structured_output()`'s internal method
selection, so the exact request shape (and the safety checks below) match what
docs/RESEARCH.md §A verified against the raw API.

Key facts this implementation depends on (verified Aug 2026, docs/RESEARCH.md §A):
- `response_mime_type` + `response_json_schema` for structured output.
- Do NOT send temperature/top_p/top_k — Gemini 3.x silently ignores them today and will
  400 on them in a future model.
- `thinking_level="low"` for extraction — this is data extraction, not reasoning.
- PDFs are sent directly as inline bytes.
- MAX_TOKENS can produce a truncated response with NO exception — checked explicitly via
  `response_metadata["finish_reason"]`, never inferred from an empty result.
"""

import base64
import json

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.models.user import AgentPersona
from app.providers.base import (
    BragDocumentInput,
    BreakdownInput,
    ConnectionStatus,
    ExtractInput,
    LLMProvider,
    ProviderError,
)
from app.providers.prompts import (
    BRAG_DOCUMENT_SYSTEM_PROMPTS,
    BREAKDOWN_SYSTEM_PROMPTS,
    EXTRACTION_SYSTEM_PROMPTS,
    REWRITE_SYSTEM_PROMPTS,
    build_brag_document_prompt,
    build_breakdown_prompt,
    build_rewrite_prompt,
)
from app.providers.schema_utils import simplify_for_gemini


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gemini-3.5-flash"):
        self._api_key = api_key
        self._model_name = model

    def _chat(self, **extra) -> ChatGoogleGenerativeAI:
        # A fresh instance per call — these are cheap wrappers, no persistent connection,
        # and it keeps this provider stateless like OpenAIProvider.
        return ChatGoogleGenerativeAI(model=self._model_name, google_api_key=self._api_key, **extra)

    async def extract(self, doc: ExtractInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        if doc.raw_bytes and doc.mime_type == "application/pdf":
            human_content = [
                {
                    "type": "media",
                    "mime_type": doc.mime_type,
                    "data": base64.b64encode(doc.raw_bytes).decode(),
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
            response_mime_type="application/json",
            response_schema=simplify_for_gemini(json_schema),
            thinking_level="low",
            max_output_tokens=8192,
        )

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=EXTRACTION_SYSTEM_PROMPTS[persona]), HumanMessage(content=human_content)]
            )
        except Exception as exc:  # langchain wraps provider errors inconsistently across versions
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "MAX_TOKENS":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "Gemini hit the output token limit before finishing — the document may "
                "be too long, or contain more projects than expected.",
                retryable=True,
            )
        if not response.text:
            raise ProviderError("EMPTY_RESPONSE", "Gemini returned no content", retryable=True)

        return json.loads(response.text)

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
        chat = self._chat(thinking_level="low", max_output_tokens=2048)

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=REWRITE_SYSTEM_PROMPTS[persona]), HumanMessage(content=prompt)]
            )
        except Exception as exc:  # langchain wraps provider errors inconsistently across versions
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        if not response.text:
            raise ProviderError("EMPTY_RESPONSE", "Gemini returned no content", retryable=True)
        return response.text.strip()

    async def propose_breakdown(
        self, doc: BreakdownInput, json_schema: dict, *, persona: AgentPersona, max_tasks: int
    ) -> dict:
        human_content: list[dict] = []
        if doc.raw_bytes and doc.mime_type == "application/pdf":
            human_content.append(
                {"type": "media", "mime_type": doc.mime_type, "data": base64.b64encode(doc.raw_bytes).decode()}
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

        # 16384, not extract()'s 8192 — a task tree runs larger, and Gemini counts
        # thinking tokens against max_output_tokens (docs/RESEARCH.md §A3.2), so the
        # extraction budget is genuinely too tight here.
        chat = self._chat(
            response_mime_type="application/json",
            response_schema=simplify_for_gemini(json_schema),
            thinking_level="low",
            max_output_tokens=16384,
        )

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=BREAKDOWN_SYSTEM_PROMPTS[persona]), HumanMessage(content=human_content)]
            )
        except Exception as exc:  # langchain wraps provider errors inconsistently across versions
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "MAX_TOKENS":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "The AI ran out of room before finishing — try again with fewer, larger tasks.",
                retryable=True,
            )
        if not response.text:
            raise ProviderError("EMPTY_RESPONSE", "Gemini returned no content", retryable=True)

        return json.loads(response.text)

    async def generate_brag_document(
        self, doc: BragDocumentInput, json_schema: dict, *, persona: AgentPersona
    ) -> dict:
        human_content = [{"type": "text", "text": build_brag_document_prompt(doc)}]

        # 16384, not extract()'s 8192 — same reasoning as propose_breakdown: a multi-
        # section brag document runs larger than 9 flat extraction fields, and Gemini
        # counts thinking tokens against max_output_tokens.
        chat = self._chat(
            response_mime_type="application/json",
            response_schema=simplify_for_gemini(json_schema),
            thinking_level="low",
            max_output_tokens=16384,
        )

        try:
            response = await chat.ainvoke(
                [
                    SystemMessage(content=BRAG_DOCUMENT_SYSTEM_PROMPTS[persona]),
                    HumanMessage(content=human_content),
                ]
            )
        except Exception as exc:  # langchain wraps provider errors inconsistently across versions
            code, retryable = _classify_error(exc)
            raise ProviderError(code, str(exc), retryable=retryable) from exc

        finish_reason = (response.response_metadata or {}).get("finish_reason")
        if finish_reason == "MAX_TOKENS":
            raise ProviderError(
                "TRUNCATED_RESPONSE",
                "The AI ran out of room before finishing the brag document — try again.",
                retryable=True,
            )
        if not response.text:
            raise ProviderError("EMPTY_RESPONSE", "Gemini returned no content", retryable=True)

        return json.loads(response.text)

    def get_chat_model(self) -> ChatGoogleGenerativeAI:
        # No response_mime_type/response_schema (those are extract()-only structured-
        # output config) and a chat-appropriate max_output_tokens — replies can run longer
        # than a rewrite snippet but shouldn't be unbounded.
        return self._chat(thinking_level="low", max_output_tokens=4096)

    async def test_connection(self) -> ConnectionStatus:
        try:
            # google-genai's list-models call is the cheap, zero-token probe (docs/RESEARCH.md
            # §A6); langchain-google-genai doesn't wrap it, so we drop to the underlying client.
            from google import genai as _genai

            client = _genai.Client(api_key=self._api_key)
            models = [m.name async for m in await client.aio.models.list()]
            return ConnectionStatus(ok=True, detail=f"OK — {len(models)} models available", models=models)
        except Exception as exc:  # noqa: BLE001
            code, _ = _classify_error(exc)
            if code == "PROVIDER_AUTH":
                return ConnectionStatus(
                    ok=False,
                    detail=(
                        "Invalid key, or this is an unrestricted 'standard' key — those "
                        "are being phased out. Create a new key at "
                        "aistudio.google.com/api-keys."
                    ),
                )
            return ConnectionStatus(ok=False, detail=f"Unreachable: {exc}")


def _classify_error(exc: Exception) -> tuple[str, bool]:
    """LangChain doesn't normalize provider exceptions across integration versions, so we
    fall back to inspecting the underlying google.genai.errors type when present, and the
    message otherwise. Verify this mapping against the installed langchain-google-genai
    version — it's the one place we couldn't lock down a stable API surface.

    PROVIDER_KEY_EXPIRED is checked ahead of both the 401/403 branch and the generic
    "api key" fallback below: Google returns an expired key as a 400 INVALID_ARGUMENT
    with "API key expired. Please renew the API key." in the message, not a 401/403, and
    that message also contains the substring "api key" — so the expired check must run
    first or it would be swallowed by the generic PROVIDER_AUTH case."""
    try:
        from google.genai import errors as genai_errors

        if isinstance(exc, genai_errors.ClientError):
            if "expired" in str(exc).lower():
                return "PROVIDER_KEY_EXPIRED", False
            if exc.code == 429:
                return "RATE_LIMITED", True
            if exc.code in (401, 403):
                return "PROVIDER_AUTH", False
            return "PROVIDER_BAD_REQUEST", False
        if isinstance(exc, genai_errors.ServerError):
            return "PROVIDER_UNAVAILABLE", True
    except ImportError:
        pass

    message = str(exc).lower()
    if "expired" in message:
        return "PROVIDER_KEY_EXPIRED", False
    if "429" in message or "quota" in message or "rate limit" in message:
        return "RATE_LIMITED", True
    if "401" in message or "403" in message or "permission" in message or "api key" in message:
        return "PROVIDER_AUTH", False
    return "PROVIDER_ERROR", False
