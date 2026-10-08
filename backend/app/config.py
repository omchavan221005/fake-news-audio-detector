"""
Centralized application settings.

All configuration is read from environment variables (see .env).
Nothing here is hardcoded to a secret value — secrets must be supplied
via the environment / .env file, which is gitignored.

Redis and Celery have been removed in favour of FastAPI BackgroundTasks +
a thread-pool worker (no external broker required for development).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database ────────────────────────────────────────────────────────────────
    database_url: str = "postgresql://fnad_user:change_me@localhost:5432/fake_news_audio_detector"

    # ── File Storage ────────────────────────────────────────────────────────────
    audio_storage_path: str = "./data/audio"
    max_upload_size_mb: int = 100
    allowed_audio_extensions: tuple[str, ...] = (".mp3", ".wav", ".m4a", ".mp4")
    allowed_audio_mime_types: tuple[str, ...] = (
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/mp4",
        "audio/x-m4a",
        "video/mp4",        # mp4 container carrying audio track
        "audio/webm",
        "video/webm",
    )

    # ── Speech-to-Text ──────────────────────────────────────────────────────────
    whisper_model_size: str = "base"   # tiny | base | small | medium | large-v3
    whisper_device: str = "cpu"         # cpu | cuda | auto
    whisper_compute_type: str = "default"  # default | int8 | float16 | float32

    # ── Claim Verification / Evidence Retrieval ─────────────────────────────────
    # Supply a real key from Serper (https://serper.dev) or Tavily (https://tavily.com).
    # Without one the verifier falls back to "insufficient evidence" gracefully.
    search_api_key: str | None = None
    search_api_provider: str | None = None   # "serper" | "tavily" | "duckduckgo"

    # ── Optional hosted LLM for claim extraction ────────────────────────────────
    # Leave blank to use the local HuggingFace pipeline instead.
    llm_api_key: str | None = None

    # ── Background worker concurrency ───────────────────────────────────────────
    # Number of threads used by the thread-pool worker that runs ML pipelines.
    worker_max_threads: int = 2

    # ── Application ─────────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"


settings = Settings()
