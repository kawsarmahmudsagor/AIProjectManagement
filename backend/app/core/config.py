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

    # Project media (models/project_media.py) is stored as Postgres bytea, not on disk,
    # so every one of these caps is also a per-request memory cap in *this* process: the
    # bytes are held once by the request handler and again while asyncpg encodes the
    # bytea parameter. max_upload_size_mb (25) governs documents only.
    max_thumbnail_size_mb: int = 5  # matches the profile-photo cap
    max_video_size_mb: int = 50
    max_chat_image_size_mb: int = 5
    # Range-response / full-body streaming chunk for video. Every chunk is one
    # `substring(data from N for L)` round-trip, so this trades round-trips against peak
    # memory; 1 MiB is ~50 queries for a max-size video.
    media_stream_chunk_bytes: int = 1024 * 1024
    # Max concurrent video uploads across the process — the one hard backstop against
    # N * max_video_size_mb resident at once.
    max_concurrent_video_uploads: int = 2

    # Video-frame carousel (services/video_frame_service.py) — how many stills to pull
    # from a project's uploaded video, and how they're encoded. Starting points, not
    # measured; adjust after seeing the carousel rendered.
    video_frame_count: int = 6
    video_frame_max_dimension_px: int = 640
    video_frame_jpeg_quality: int = 78

    # Text-to-image model for AI project thumbnails (providers/gemini.generate_image).
    # Set to "" to hard-disable the raster path so every generation takes the
    # deterministic SVG-poster route (services/poster_renderer.py) — that's the switch to
    # flip if this model id turns out not to be enabled for an account's tier.
    gemini_image_model: str = "imagen-4.0-generate-001"

    saq_concurrency: int = 4

    openai_default_model: str = "gpt-4.1-mini"
    gemini_default_model: str = "gemini-3.5-flash"

    # Jarvis's github_search tool (app/agents/chat_tools.py). A single shared app-level
    # token, not per-user — if unset, the tool still works but degrades to GitHub's
    # unauthenticated rate limit (10 req/min to /search/*) rather than hard-failing.
    github_token: str | None = None
    github_min_stars: int = 200
    github_freshness_months: int = 12

    # Proactive suggestions background feature (app/services/suggestion_service.py).
    github_suggestion_cache_ttl_hours: int = 12
    github_suggestions_ttl_hours: int = 24
    github_suggestions_debounce_hours: int = 6
    github_suggestions_top_technologies: int = 5
    github_suggestions_repos_per_technology: int = 3
    github_suggestions_cron_batch_size: int = 10
    github_suggestions_min_call_interval_seconds: float = 2.5
    # How far back the Dashboard card's "recent" view looks (the Conversations page's
    # Suggestions section has no such window — it shows the full history instead) — see
    # suggestion_service.list_suggestions's `scope` parameter.
    github_suggestions_dashboard_window_hours: int = 24

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


# AI work-breakdown (services/breakdown_service.py) T-shirt-size default estimates, in
# minutes. The model only ever emits xs/s/m/l/xl (an enum can't hallucinate "13.5 hours");
# this is the one deterministic place that maps a size to a number, and it's only ever a
# *default* for the editable hours field on each review row — never summed or shown as a
# schedule (backend/DESIGN.md §8's "no rollup total" rule). A plain module constant, not a
# Settings field, since it's a product/tuning knob reviewed in code, not an env var.
BREAKDOWN_ESTIMATE_SIZE_MINUTES: dict[str, int] = {
    "xs": 30,
    "s": 120,
    "m": 240,
    "l": 480,
    "xl": 960,
}
