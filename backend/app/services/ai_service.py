"""Backs POST /ai/rewrite. Holds the generate-then-verify-then-retry loop for the 390-char
short-summary cap (backend/DESIGN.md §4) — neither provider can be trusted to hit an exact
character count on the first try, so we ask again with the overage stated, up to 3
attempts, then fall back to a sentence-boundary truncation as a last resort.
"""

import re

from app.agents.rewrite_graph import run_rewrite
from app.core.richtext import html_to_text, sanitize_html, wrap_html
from app.models.user import AgentPersona
from app.providers.base import LLMProvider

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def truncate_at_sentence(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    sentences = _SENTENCE_END.split(text)
    out = ""
    for sentence in sentences:
        candidate = f"{out} {sentence}".strip()
        if len(candidate) > limit:
            break
        out = candidate
    return out or text[:limit].rsplit(" ", 1)[0]


async def rewrite_field(
    provider: LLMProvider,
    *,
    op: str,
    target_html: str,
    source_html: str,
    char_limit: int | None,
    context: dict | None = None,
    instruction: str | None = None,
    persona: AgentPersona,
) -> tuple[str, str]:
    target_text = html_to_text(target_html)
    source_text = html_to_text(source_html) or target_text

    if op != "generate-short" or not char_limit:
        draft = await run_rewrite(
            provider,
            persona,
            op=op,
            target_text=target_text,
            source_text=source_text,
            char_limit=char_limit,
            context=context,
            instruction=instruction,
        )
        html = sanitize_html(wrap_html(draft))
        return html, html_to_text(html)

    working_source = source_text
    draft = ""
    for attempt in range(3):
        draft = await run_rewrite(
            provider,
            persona,
            op=op,
            target_text=target_text,
            source_text=working_source,
            char_limit=char_limit,
            context=context,
            instruction=instruction,
        )
        if len(draft) <= char_limit:
            html = sanitize_html(wrap_html(draft))
            return html, html_to_text(html)
        overage = len(draft) - char_limit
        working_source = (
            f"{source_text}\n\n(Previous attempt was {len(draft)} characters, "
            f"{overage} over the {char_limit} limit — be more concise.)"
        )

    truncated = truncate_at_sentence(draft, char_limit)
    html = sanitize_html(wrap_html(truncated))
    return html, html_to_text(html)
