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

# Local-only gemma4 variants — no `-cloud` tags, so these run full local inference and
# support structured output for extraction with no fallback substitution needed
# (see is_ollama_cloud_model / registry.get_provider's purpose="extract" handling,
# which stays in place as a safety net for anyone configuring a cloud model manually).
OLLAMA_MODELS = [
    "gemma4:e2b",
    "gemma4:e4b",
]
OLLAMA_DEFAULT_MODEL = "gemma4:e2b"
