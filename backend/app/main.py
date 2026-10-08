"""
FastAPI application entry-point.

Wires together:
  - CORS middleware
  - API routers (audio, analyze)
  - DB table creation on startup (use Alembic migrations in production)
  - Background thread-pool worker lifecycle
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("fnad")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────────
    logger.info("Creating database tables (if not already present)…")
    # Import all models so SQLAlchemy's metadata is populated before create_all
    import app.models.models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready.")

    import os
    os.makedirs(settings.audio_storage_path, exist_ok=True)
    logger.info("Audio storage directory: %s", settings.audio_storage_path)

    yield  # ── Application runs ──────────────────────────────────────────────

    # ── Shutdown ───────────────────────────────────────────────────────────────
    from app.workers.celery_app import shutdown
    shutdown(wait=False)
    logger.info("Background worker shut down.")


app = FastAPI(
    title="Fake News Detection from Audio",
    description=(
        "End-to-end pipeline: Audio → Speech-to-Text → Claim Extraction → "
        "Fact Verification → AI-Audio Detection → Dashboard"
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",   # Vite dev server
        "http://localhost:5174",   # Vite dev server (fallback port)
        "http://localhost:5175",   # Vite dev server (fallback port)
        "http://localhost:5176",   # Vite dev server (fallback port)
        "http://localhost:3000",   # Alternative dev port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────
from app.api.audio import router as audio_router       # noqa: E402
from app.api.analyze import router as analyze_router   # noqa: E402

app.include_router(audio_router,   prefix="/api/audio",   tags=["Audio Upload & Streaming"])
app.include_router(analyze_router, prefix="/api/analyze", tags=["Analysis Jobs"])


# ── Health check ───────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
@app.get("/api/health", tags=["System"])
def health_check():
    """Liveness probe — confirms the API is up and config is loaded."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "whisper_model_size": settings.whisper_model_size,
        "whisper_device": settings.whisper_device,
        "worker_threads": settings.worker_max_threads,
    }
