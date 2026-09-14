"""Static model catalogues shown in the provider settings UI's "Models" dropdown
(frontend/components/settings/provider-card.tsx).
"""

GEMINI_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.1-pro-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.5-pro",
]
GEMINI_DEFAULT_MODEL = "gemini-3.5-flash"

OPENAI_MODELS = [
    "gpt-5.6",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]
OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"

# Input-token context windows, used only to size the chat-history compaction budget
# (services/chat_service.should_compact) — never to size an actual request. gpt-4o/
# gpt-4o-mini (128K) and the gpt-4.1 family (~1.05M) are long-established figures; the
# gpt-5.x and gemini-3.x figures came from a live web search at design time (they
# postdate this codebase's LLM training data) and should be spot-checked against each
# provider's own published docs before trusting them for anything beyond this soft
# compaction gate — same "verify against what's actually installed" discipline
# gemini.py/openai.py already apply to response_metadata shapes. Any model missing here
# (a future catalog addition, or a typo) falls back to _DEFAULT_CONTEXT_WINDOW, which
# fails safe: compacting too early costs a little, silently overflowing costs a turn.
_DEFAULT_CONTEXT_WINDOW = 128_000

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    "gemini-3.7-flash": 1_048_576,
    "gemini-3.6-flash": 1_048_576,
    "gemini-3.5-flash": 1_048_576,
    "gemini-3.5-flash-lite": 1_048_576,
    "gemini-3.1-flash-lite": 1_048_576,
    "gemini-3.1-pro-preview": 1_048_576,
    "gemini-2.5-flash": 1_048_576,
    "gemini-2.5-flash-lite": 1_048_576,
    "gemini-2.5-pro": 1_048_576,
    "gpt-5.6": 1_048_576,
    "gpt-5.5": 1_048_576,
    "gpt-5.4": 1_048_576,
    "gpt-5.4-mini": 1_048_576,
    "gpt-4.1": 1_047_576,
    "gpt-4.1-mini": 1_047_576,
    "gpt-4.1-nano": 1_047_576,
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
}


def context_window_for(model: str) -> int:
    return MODEL_CONTEXT_WINDOWS.get(model, _DEFAULT_CONTEXT_WINDOW)
