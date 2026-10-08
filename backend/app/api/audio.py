"""
Audio API router — Phase 3.

Endpoints:
  POST /api/audio/upload          — validate, store, create DB record
  POST /api/audio/{id}/analyze    — dispatch background analysis job
  GET  /api/audio/{id}/stream     — HTTP Range streaming for browser player
  GET  /api/audio/{id}            — fetch audio file metadata
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.schemas import AudioFileResponse, JobCreateResponse
from app.services.audio_service import (
    save_uploaded_audio,
    get_audio_file_or_404,
    stream_audio_file,
)
from app.services.job_service import create_job
from app.models.models import JobStatus

logger = logging.getLogger("fnad.api.audio")

router = APIRouter()


@router.post(
    "/upload",
    response_model=AudioFileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an audio file",
    description=(
        "Accepts MP3, WAV, M4A, or MP4 audio files up to the configured size limit. "
        "Validates the file by magic-byte inspection (not just extension). "
        "Returns stored metadata including detected duration and sample rate."
    ),
)
async def upload_audio(
    file: UploadFile = File(..., description="Audio file to analyse"),
    db: Session = Depends(get_db),
):
    audio_file = await save_uploaded_audio(file, db)
    return AudioFileResponse(
        audio_file_id=audio_file.id,
        filename=audio_file.original_filename,
        mime_type=audio_file.mime_type,
        file_size_bytes=audio_file.file_size_bytes,
        duration_seconds=audio_file.duration_seconds,
        sample_rate=audio_file.sample_rate,
        uploaded_at=audio_file.uploaded_at,
    )


@router.post(
    "/{audio_file_id}/analyze",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start analysis job for an uploaded audio file",
)
def start_analysis(
    audio_file_id: str,
    db: Session = Depends(get_db),
):
    """
    Creates an AnalysisJob and dispatches the ML pipeline to the background
    thread-pool worker. Returns immediately with the job_id for polling.
    """
    audio_file = get_audio_file_or_404(audio_file_id, db)
    job = create_job(audio_file, db)

    # Import here to avoid circular imports; pipeline_runner is registered in main.py
    from app.workers.tasks import run_analysis_pipeline
    from app.workers.celery_app import submit_task

    submit_task(run_analysis_pipeline, str(job.id))

    return JobCreateResponse(
        job_id=job.id,
        audio_file_id=audio_file.id,
        status=JobStatus.PENDING,
        message="Analysis job queued. Poll /api/analyze/{job_id}/status for progress.",
    )


@router.get(
    "/{audio_file_id}",
    response_model=AudioFileResponse,
    summary="Get audio file metadata",
)
def get_audio_metadata(
    audio_file_id: str,
    db: Session = Depends(get_db),
):
    audio_file = get_audio_file_or_404(audio_file_id, db)
    return AudioFileResponse(
        audio_file_id=audio_file.id,
        filename=audio_file.original_filename,
        mime_type=audio_file.mime_type,
        file_size_bytes=audio_file.file_size_bytes,
        duration_seconds=audio_file.duration_seconds,
        sample_rate=audio_file.sample_rate,
        uploaded_at=audio_file.uploaded_at,
    )


@router.get(
    "/{audio_file_id}/stream",
    summary="Stream audio file with HTTP Range support",
)
async def stream_audio(
    audio_file_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Streams the uploaded audio file supporting HTTP Range requests so that
    the browser's <audio> element can seek to any position without reloading
    the entire file.
    """
    audio_file = get_audio_file_or_404(audio_file_id, db)
    range_header = request.headers.get("range")

    headers, http_status, byte_gen = await stream_audio_file(audio_file, range_header)

    return StreamingResponse(
        byte_gen,
        status_code=http_status,
        headers=headers,
        media_type=audio_file.mime_type,
    )
