"""Provider-agnostic token-count *estimate* for gating chat-history compaction
(services/chat_service.py's should_compact). Uses a single OpenAI tokenizer
(`o200k_base`, the encoding gpt-4o/4.1/5.x use) as a stand-in for both Gemini and
OpenAI rather than each provider's own tokenizer — Gemini has no offline tokenizer and
calling its `count_tokens` API would add a network round-trip to a path that runs on
every turn. This is deliberately an approximation good enough to gate a background job,
never a billing-accurate count (see services/usage_service.py for the actual
provider-reported token counts used for cost tracking).
"""

from langchain_core.messages import BaseMessage
from tiktoken import get_encoding

_ENCODING = get_encoding("o200k_base")

# Rough per-message formatting overhead (role marker, separators) that content length
# alone doesn't capture — not trying to reproduce any provider's exact chat template.
_PER_MESSAGE_OVERHEAD_TOKENS = 4

# An image content block (providers/content_blocks.py) contributes no characters to
# _stringify_content below but costs real input tokens once actually sent to a model. A
# flat per-image estimate is enough for a soft compaction gate — same "fails safe"
# reasoning as catalog.py's _DEFAULT_CONTEXT_WINDOW fallback: under-counting only risks
# compacting a little late (costs at most one turn), never overflowing the model's
# window outright, since should_compact's COMPACTION_TOKEN_FRACTION already leaves
# headroom below the real limit.
_IMAGE_BLOCK_TOKENS = 800


def _stringify_content(content: str | list) -> tuple[str, int]:
    """Deliberately duplicated from agents/chatbot_graph.stringify_content rather than
    imported: providers/ sits below agents/ in this app's layering (agents/chatbot_graph
    imports LLMProvider from providers/base), so importing the other way round here
    would invert that dependency. Same logic — a model's content is str | list[str |
    dict], only text blocks matter for the text half; returns (text, image_block_count)
    since a caller here also needs to know how many image blocks to charge for."""
    if isinstance(content, str):
        return content, 0
    parts: list[str] = []
    image_count = 0
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif isinstance(block, dict) and block.get("type") == "image":
            image_count += 1
    return "".join(parts), image_count


def estimate_tokens(messages: list[BaseMessage]) -> int:
    total = 0
    for message in messages:
        text, image_count = _stringify_content(message.content)
        total += len(_ENCODING.encode(text)) + _PER_MESSAGE_OVERHEAD_TOKENS + image_count * _IMAGE_BLOCK_TOKENS
    return total
