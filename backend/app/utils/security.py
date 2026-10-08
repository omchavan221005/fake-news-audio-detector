"""
Security utilities for safe file handling.

- Sanitizes filenames to prevent directory traversal attacks.
- Validates MIME type against magic bytes (not just the extension).
- Generates UUID-based storage paths to prevent filename collisions.
"""
from __future__ import annotations

import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path

logger = logging.getLogger("fnad.security")

# Characters that are safe in filenames
_SAFE_FILENAME_RE = re.compile(r"[^\w\-. ]")


def sanitize_filename(original: str) -> str:
    """
    Strip path separators and dangerous characters from a user-supplied filename.
    Returns only the basename with unsafe chars replaced by underscores.
    """
    # Take only the basename (never allow path components)
    basename = os.path.basename(original)
    # Replace unsafe chars
    safe = _SAFE_FILENAME_RE.sub("_", basename)
    # Collapse consecutive underscores/spaces
    safe = re.sub(r"[_\s]{2,}", "_", safe).strip("_. ")
    return safe or "upload"


def generate_storage_path(storage_root: str, original_filename: str) -> tuple[str, str]:
    """
    Generate a collision-free storage path using UUID4.

    Returns (absolute_path, relative_storage_path).
    The relative path is what gets saved in the database.

    Directory layout: <storage_root>/<uuid>/<safe_original_filename>
    """
    file_id = uuid.uuid4()
    safe_name = sanitize_filename(original_filename)
    ext = Path(original_filename).suffix.lower()

    # If sanitization ate the extension, re-append it
    if not safe_name.endswith(ext):
        safe_name = safe_name + ext

    relative_path = os.path.join(str(file_id), safe_name)
    absolute_path = os.path.join(storage_root, relative_path)
    return absolute_path, relative_path


def get_extension(filename: str) -> str:
    """Return the lowercase extension including the leading dot, e.g. '.mp3'."""
    return Path(filename).suffix.lower()


def read_magic_bytes(file_header: bytes) -> str | None:
    """
    Attempt to identify MIME type from the first bytes of the file.

    We check the most common audio magic byte signatures ourselves to avoid
    platform-specific dependencies on libmagic on Windows.

    Returns a MIME-type string or None if unrecognised.
    """
    h = file_header

    # MP3: ID3 tag or raw frame sync (0xFF 0xFB / 0xFF 0xF3 / 0xFF 0xF2)
    if h[:3] == b"ID3" or (len(h) >= 2 and h[0] == 0xFF and h[1] in (0xFB, 0xF3, 0xF2, 0xE3)):
        return "audio/mpeg"

    # WAV: RIFF....WAVE
    if h[:4] == b"RIFF" and h[8:12] == b"WAVE":
        return "audio/wav"

    # MP4 / M4A: ftyp box (bytes 4-8 = b"ftyp")
    if len(h) >= 12 and h[4:8] == b"ftyp":
        brand = h[8:12]
        if brand in (b"M4A ", b"M4B ", b"mp42", b"mp41", b"isom", b"iso2"):
            return "audio/mp4"
        return "video/mp4"   # generic mp4 container

    # OGG (Vorbis / Opus)
    if h[:4] == b"OggS":
        return "audio/ogg"

    # FLAC
    if h[:4] == b"fLaC":
        return "audio/flac"

    # WebM / MKV (EBML magic)
    if h[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"

    return None


def validate_audio_file(
    filename: str,
    file_header: bytes,
    file_size_bytes: int,
    allowed_extensions: tuple[str, ...],
    allowed_mime_types: tuple[str, ...],
    max_size_mb: int,
) -> tuple[bool, str, str | None]:
    """
    Validate an uploaded file.

    Returns (is_valid, error_message_or_empty, detected_mime_type).
    """
    # 1. Extension check
    ext = get_extension(filename)
    if ext not in allowed_extensions:
        return False, f"File extension '{ext}' is not allowed. Allowed: {', '.join(allowed_extensions)}", None

    # 2. File-size check
    max_bytes = max_size_mb * 1024 * 1024
    if file_size_bytes > max_bytes:
        return False, f"File exceeds maximum allowed size of {max_size_mb} MB.", None

    # 3. Magic-byte MIME check
    detected_mime = read_magic_bytes(file_header)

    if detected_mime is None:
        # Magic bytes returned None = the file header does not match any known
        # audio format signature. Real MP3/WAV/M4A files always have detectable
        # headers — reject unconditionally to prevent spoofed extensions.
        return (
            False,
            "File content could not be identified as a valid audio format. "
            "Please upload a real MP3, WAV, M4A, or MP4 audio file.",
            None,
        )

    if detected_mime not in allowed_mime_types:
        return (
            False,
            f"File content does not match an allowed audio type (detected: {detected_mime}). "
            "Ensure you are uploading a real audio file.",
            detected_mime,
        )

    return True, "", detected_mime
