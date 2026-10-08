"""
Audio service — handles:
  1. Receiving an uploaded audio file from FastAPI
  2. Running full security validation (extension, magic bytes, size)
  3. Persisting the file to disk with a UUID-based path
  4. Extracting audio metadata (duration, sample-rate) via mutagen
  5. Writing the AudioFile record to the database
  6. Serving HTTP Range-based audio streaming
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import AsyncGenerator

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import AudioFile
from app.utils.security import generate_storage_path, validate_audio_file

logger = logging.getLogger("fnad.audio_service")

# How many bytes we read upfront to sniff magic bytes (64 is sufficient for any format we support)
_MAGIC_HEADER_SIZE = 64
# Streaming chunk size for HTTP Range delivery (256 KB)
_STREAM_CHUNK = 256 * 1024


def _extract_audio_metadata(file_path: str) -> dict:
    """
    Use mutagen to extract duration and sample-rate from a stored audio file.
    Returns a dict with keys: duration_seconds, sample_rate.
    Falls back to None values if the file is unreadable by mutagen.
    """
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(file_path)
        if audio is None:
            return {"duration_seconds": None, "sample_rate": None}

        duration = getattr(audio.info, "length", None)
        sample_rate = getattr(audio.info, "sample_rate", None)
        return {"duration_seconds": round(duration, 3) if duration else None, "sample_rate": sample_rate}
    except Exception as exc:
        logger.warning("mutagen could not read metadata from %s: %s", file_path, exc)
        return {"duration_seconds": None, "sample_rate": None}


async def save_uploaded_audio(upload: UploadFile, db: Session) -> AudioFile:
    """
    Validate, store, and register an uploaded audio file.

    Raises HTTPException on any validation failure.
    Returns the persisted AudioFile ORM object.
    """
    original_name = upload.filename or "unknown_upload"

    # ── 1. Read the file into memory (up to max_size + 1 byte to detect oversize) ──
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    # Read header bytes first for magic-byte check without loading entire file
    header = await upload.read(_MAGIC_HEADER_SIZE)
    rest = await upload.read(max_bytes - _MAGIC_HEADER_SIZE + 1)
    file_bytes = header + rest

    total_size = len(file_bytes)

    # ── 2. Validate ─────────────────────────────────────────────────────────────
    is_valid, error_msg, detected_mime = validate_audio_file(
        filename=original_name,
        file_header=header,
        file_size_bytes=total_size,
        allowed_extensions=settings.allowed_audio_extensions,
        allowed_mime_types=settings.allowed_audio_mime_types,
        max_size_mb=settings.max_upload_size_mb,
    )
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error_msg)

    # ── 3. Generate storage path and create directories ─────────────────────────
    abs_path, rel_path = generate_storage_path(settings.audio_storage_path, original_name)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    # ── 4. Write file to disk ────────────────────────────────────────────────────
    try:
        with open(abs_path, "wb") as f:
            f.write(file_bytes)
        logger.info("Stored audio file: %s (%d bytes)", abs_path, total_size)
    except OSError as exc:
        logger.error("Failed to write audio file: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store audio file. Please try again.",
        )

    # ── 5. Extract audio metadata ────────────────────────────────────────────────
    metadata = _extract_audio_metadata(abs_path)

    # ── 6. Persist DB record ─────────────────────────────────────────────────────
    audio_file = AudioFile(
        original_filename=original_name,
        storage_path=rel_path,
        mime_type=detected_mime or "application/octet-stream",
        file_size_bytes=total_size,
        duration_seconds=metadata["duration_seconds"],
        sample_rate=metadata["sample_rate"],
    )
    db.add(audio_file)
    db.commit()
    db.refresh(audio_file)

    logger.info(
        "AudioFile created: id=%s filename=%s duration=%.1fs",
        audio_file.id,
        original_name,
        metadata["duration_seconds"] or 0.0,
    )
    return audio_file


def get_audio_file_or_404(audio_file_id: str, db: Session) -> AudioFile:
    """Fetch an AudioFile record by UUID or raise 404."""
    import uuid as _uuid
    try:
        uid = _uuid.UUID(audio_file_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found.")

    record = db.query(AudioFile).filter(AudioFile.id == uid).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file not found.")
    return record


def resolve_storage_path(relative_path: str) -> str:
    """Resolve a DB-stored relative path to an absolute filesystem path."""
    return os.path.join(settings.audio_storage_path, relative_path)


async def stream_audio_file(
    audio_file: AudioFile,
    range_header: str | None,
) -> tuple[dict, AsyncGenerator]:
    """
    Stream an audio file with HTTP Range support.

    Returns (response_headers, async_byte_generator).
    The generator yields chunks of the file for the requested byte range.
    """
    abs_path = resolve_storage_path(audio_file.storage_path)

    if not os.path.exists(abs_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file missing from storage.")

    file_size = os.path.getsize(abs_path)
    start = 0
    end = file_size - 1

    # Parse Range header: "bytes=<start>-<end>"
    status_code = 200
    if range_header:
        try:
            range_spec = range_header.replace("bytes=", "")
            parts = range_spec.split("-")
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])
            status_code = 206  # Partial Content
        except (ValueError, IndexError):
            pass  # serve full file on malformed Range header

    # Clamp to file boundaries
    start = max(0, start)
    end = min(end, file_size - 1)
    content_length = end - start + 1

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": audio_file.mime_type,
    }

    async def _byte_generator() -> AsyncGenerator[bytes, None]:
        with open(abs_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(_STREAM_CHUNK, remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return headers, status_code, _byte_generator()


def delete_audio_file(audio_file: AudioFile, db: Session) -> None:
    """
    Remove the audio file from disk and delete the DB record.
    Used for cleanup on failed jobs or explicit deletion.
    """
    abs_path = resolve_storage_path(audio_file.storage_path)
    parent_dir = os.path.dirname(abs_path)
    try:
        if os.path.exists(parent_dir):
            shutil.rmtree(parent_dir)
    except OSError as exc:
        logger.warning("Could not remove audio directory %s: %s", parent_dir, exc)

    db.delete(audio_file)
    db.commit()
    logger.info("Deleted audio file %s", audio_file.id)
