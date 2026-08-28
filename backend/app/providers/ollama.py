"""Ollama provider, orchestrated through LangChain (`langchain-ollama`).

We bind Ollama's native `format` parameter directly (via `ChatOllama(format=...)`) rather
than depending on `.with_structured_output()`'s internal method selection — there is a
documented, currently-open issue where `with_structured_output` on ChatOllama has not
been honoured in some versions while the raw `format` parameter always works
(langchain-ai/langchain#29410). Binding `format` ourselves sidesteps that entirely and
matches exactly what docs/RESEARCH.md §B verified against the raw Ollama API.

Local-only: Ollama Cloud does not support structured outputs as of Aug 2026
(docs/RESEARCH.md §B3), so extract() refuses to run against a base_url that looks like
Ollama Cloud rather than silently degrading.

The single biggest correctness risk here is silent context truncation: Ollama's default
num_ctx is 4096 tokens and it truncates server-side with a normal 200 response. Every
call sets num_ctx explicitly and checks `prompt_eval_count` in `response_metadata`
afterward — verify that key name against the installed langchain-ollama version, since
LangChain otherwise just forwards Ollama's raw response dict and hasn't always kept that
stable across releases. Truncation is detected by `prompt_eval_count` landing at the
requested num_ctx ceiling (docs/RESEARCH.md §B6), not by comparing against our own
chars/3 token estimate — that estimate is deliberately conservative and routinely
overshoots the model's real tokenizer count, so comparing against it produces false
positives on documents that were never actually truncated.
"""

import json

from httpx import ConnectError, TimeoutException
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from ollama import AsyncClient

from app.models.user import AgentPersona
from app.providers.base import ConnectionStatus, ExtractInput, LLMProvider, ProviderError
from app.providers.prompts import (
    EXTRACTION_SYSTEM_PROMPTS,
    REWRITE_SYSTEM_PROMPTS,
    build_rewrite_prompt,
    extraction_schema_prompt,
)

_CLOUD_HOSTS = ("ollama.com",)
_DEFAULT_NUM_CTX = 8192
_MAX_NUM_CTX = 65536
_EXTRACT_NUM_PREDICT = 16384
_REWRITE_NUM_PREDICT = 2048


def _next_pow2(n: int) -> int:
    return 1 << max(13, n - 1).bit_length()  # floor at 8192


def _is_cloud(base_url: str) -> bool:
    return any(host in base_url for host in _CLOUD_HOSTS)


def is_ollama_cloud_model(model: str) -> bool:
    """Ollama's local `-cloud` model proxy (docs/RESEARCH.md §B3) forwards the request to
    Ollama's hosted infra even when base_url is localhost, so a `-cloud`/`:cloud` model
    tag carries the exact same "no structured output" limitation as an actual Ollama
    Cloud base_url — checking base_url alone misses it entirely."""
    tag = model.split(":", 1)[1] if ":" in model else ""
    return tag == "cloud" or tag.endswith("-cloud")


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str, model: str, api_key: str | None = None):
        self._base_url = base_url
        self._model = model
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        # Used only for /api/show (context-length lookup) and /api/tags (connection
        # test) — langchain-ollama doesn't wrap either, so we keep the native client
        # around for those two calls.
        self._raw_client = AsyncClient(host=base_url, headers=self._headers, timeout=180)

    def _chat(self, *, num_ctx: int, num_predict: int, temperature: float, format: dict | None = None) -> ChatOllama:
        return ChatOllama(
            model=self._model,
            base_url=self._base_url,
            client_kwargs={"headers": self._headers} if self._headers else None,
            num_ctx=num_ctx,
            num_predict=num_predict,
            temperature=temperature,
            format=format,
        )

    async def _resolve_num_ctx(self, estimated_tokens: int) -> int:
        try:
            info = await self._raw_client.show(self._model)
            model_ctx = (info.model_info or {}).get(f"{info.details.family}.context_length", _MAX_NUM_CTX)
        except Exception:  # noqa: BLE001 — fall back to a safe default if /api/show fails
            model_ctx = _MAX_NUM_CTX
        return min(max(_DEFAULT_NUM_CTX, _next_pow2(estimated_tokens)), model_ctx, _MAX_NUM_CTX)

    async def extract(self, doc: ExtractInput, json_schema: dict, *, persona: AgentPersona) -> dict:
        if _is_cloud(self._base_url) or is_ollama_cloud_model(self._model):
            raise ProviderError(
                "PROVIDER_UNSUPPORTED",
                f"'{self._model}' runs on Ollama Cloud, which doesn't support structured "
                "output — pick a local (non-cloud) model for extraction (docs/RESEARCH.md §B3).",
            )
        if not doc.extracted_text:
            raise ProviderError(
                "NO_TEXT_FOUND",
                "No extractable text — Ollama has no document-vision path for scanned "
                "PDFs, switch to Gemini or upload a text-based document.",
            )

        text = doc.extracted_text
        est_tokens = len(text) // 3 + 1500
        num_ctx = await self._resolve_num_ctx(est_tokens)

        prompt = f"{extraction_schema_prompt(json_schema)}\n\nDocument:\n{text}"
        chat = self._chat(num_ctx=num_ctx, num_predict=_EXTRACT_NUM_PREDICT, temperature=0, format=json_schema)

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=EXTRACTION_SYSTEM_PROMPTS[persona]), HumanMessage(content=prompt)]
            )
        except (ConnectError, TimeoutException) as exc:
            raise ProviderError("PROVIDER_UNREACHABLE", f"Ollama isn't responding: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("PROVIDER_ERROR", str(exc)) from exc

        # Real truncation looks like prompt_eval_count landing at the num_ctx ceiling
        # (docs/RESEARCH.md §B6) — comparing against our own chars/3 estimate instead
        # produced false positives, since that estimate is deliberately conservative and
        # routinely overshoots what the model's real tokenizer counts (e.g. 3196 actual
        # vs. 3920 estimated on a document nowhere near num_ctx).
        prompt_eval_count = (response.response_metadata or {}).get("prompt_eval_count", 0)
        if prompt_eval_count and prompt_eval_count >= num_ctx - 8:
            raise ProviderError(
                "TRUNCATED_INPUT",
                f"Ollama hit the {num_ctx}-token context ceiling while processing this "
                "document — it was likely truncated. Try Gemini for long documents, or "
                "raise num_ctx.",
                retryable=True,
            )

        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "Ollama returned no content", retryable=True)
        try:
            return json.loads(response.content)
        except json.JSONDecodeError as exc:
            raise ProviderError(
                "INVALID_JSON",
                f"Ollama returned content that wasn't valid JSON: {str(response.content)[:200]!r}",
                retryable=True,
            ) from exc

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
        chat = self._chat(num_ctx=_DEFAULT_NUM_CTX, num_predict=_REWRITE_NUM_PREDICT, temperature=0.3)

        try:
            response = await chat.ainvoke(
                [SystemMessage(content=REWRITE_SYSTEM_PROMPTS[persona]), HumanMessage(content=prompt)]
            )
        except (ConnectError, TimeoutException) as exc:
            raise ProviderError("PROVIDER_UNREACHABLE", f"Ollama isn't responding: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise ProviderError("PROVIDER_ERROR", str(exc)) from exc

        if not response.content:
            raise ProviderError("EMPTY_RESPONSE", "Ollama returned no content", retryable=True)
        return str(response.content).strip()

    async def test_connection(self) -> ConnectionStatus:
        try:
            tags = await self._raw_client.list()  # GET /api/tags
            models = [m.model for m in tags.models]
            return ConnectionStatus(ok=True, detail=f"OK — {len(models)} model(s) installed", models=models)
        except (ConnectError, TimeoutException):
            return ConnectionStatus(
                ok=False,
                detail=f"Ollama not reachable at {self._base_url}. Is it running?",
            )
        except Exception as exc:  # noqa: BLE001
            return ConnectionStatus(ok=False, detail=f"Unreachable: {exc}")
