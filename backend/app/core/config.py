from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "development"
    secret_key: str
    fernet_key: str

    database_url: str

    cors_origins: str = "http://localhost:3000"

    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    data_dir: Path = Path("./data")
    max_upload_size_mb: int = 25

    saq_concurrency: int = 4

    ollama_default_base_url: str = "http://localhost:11434"
    ollama_default_model: str = "gemma4:e2b"
    # Safety net only: if ollama_default_model or a user's saved default_model is ever a
    # `-cloud` tag, registry.get_provider() substitutes this local model for extraction
    # specifically (Ollama Cloud doesn't support structured output — see
    # providers/ollama.py is_ollama_cloud_model and docs/RESEARCH.md §B3). Not normally
    # reached since the Settings dropdown only offers local gemma4 models.
    ollama_extraction_fallback_model: str = "gemma4:e2b"
    gemini_default_model: str = "gemini-3.5-flash"

    # Jarvis's github_search tool (app/agents/chat_tools.py). A single shared app-level
    # token, not per-user — if unset, the tool still works but degrades to GitHub's
    # unauthenticated rate limit (10 req/min to /search/*) rather than hard-failing.
    github_token: str | None = None
    github_min_stars: int = 200
    github_freshness_months: int = 12

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.exports_dir.mkdir(parents=True, exist_ok=True)
    return settings
