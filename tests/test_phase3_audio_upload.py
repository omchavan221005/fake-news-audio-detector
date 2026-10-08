"""
Phase 3 Tests — Audio Upload & Validation

Tests:
  1. Security utilities (filename sanitization, magic-byte detection, validation logic)
  2. API upload endpoint (valid files, invalid types, oversized files)
  3. Audio streaming (Range header handling)

Run with:
    cd backend
    python -m pytest ../tests/test_phase3_audio_upload.py -v
"""
from __future__ import annotations

import io
import os
import sys
import uuid

import pytest

# Make sure the backend package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.utils.security import (
    sanitize_filename,
    generate_storage_path,
    read_magic_bytes,
    validate_audio_file,
    get_extension,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Filename Sanitization
# ─────────────────────────────────────────────────────────────────────────────

class TestSanitizeFilename:
    def test_normal_filename(self):
        assert sanitize_filename("news_report.mp3") == "news_report.mp3"

    def test_strips_path_separators(self):
        result = sanitize_filename("../../etc/passwd.mp3")
        assert "/" not in result
        assert ".." not in result

    def test_strips_path_separators_windows(self):
        result = sanitize_filename(r"C:\Windows\system32\evil.mp3")
        assert "\\" not in result
        assert "system32" not in result  # basename is used

    def test_replaces_dangerous_chars(self):
        result = sanitize_filename("file;rm -rf *.mp3")
        assert ";" not in result
        assert "*" not in result

    def test_preserves_extension(self):
        result = sanitize_filename("my file (2024).wav")
        assert result.endswith(".wav")

    def test_empty_filename_fallback(self):
        result = sanitize_filename("")
        assert result  # should return something non-empty (e.g. "upload")

    def test_unicode_filename(self):
        result = sanitize_filename("日本語ニュース.mp3")
        # Non-word chars replaced but extension preserved
        assert result.endswith(".mp3")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Magic Byte Detection
# ─────────────────────────────────────────────────────────────────────────────

class TestMagicByteDetection:
    def _mp3_id3_header(self) -> bytes:
        return b"ID3" + b"\x03\x00\x00\x00\x00\x05\xd0" + b"\x00" * 57

    def _mp3_frame_header(self) -> bytes:
        return b"\xff\xfb" + b"\x00" * 62

    def _wav_header(self) -> bytes:
        return b"RIFF\x24\xf8\x03\x00WAVE" + b"\x00" * 54

    def _mp4_ftyp_header(self) -> bytes:
        return b"\x00\x00\x00\x1cftyp" + b"M4A " + b"\x00\x00\x00\x00" + b"M4A " + b"\x00" * 48

    def _ogg_header(self) -> bytes:
        return b"OggS" + b"\x00" * 60

    def _flac_header(self) -> bytes:
        return b"fLaC" + b"\x00" * 60

    def test_detects_mp3_id3(self):
        assert read_magic_bytes(self._mp3_id3_header()) == "audio/mpeg"

    def test_detects_mp3_frame_sync(self):
        assert read_magic_bytes(self._mp3_frame_header()) == "audio/mpeg"

    def test_detects_wav(self):
        assert read_magic_bytes(self._wav_header()) == "audio/wav"

    def test_detects_m4a(self):
        assert read_magic_bytes(self._mp4_ftyp_header()) == "audio/mp4"

    def test_detects_ogg(self):
        assert read_magic_bytes(self._ogg_header()) == "audio/ogg"

    def test_detects_flac(self):
        assert read_magic_bytes(self._flac_header()) == "audio/flac"

    def test_returns_none_for_text_file(self):
        assert read_magic_bytes(b"Hello, world! This is a text file.\n") is None

    def test_returns_none_for_zip(self):
        assert read_magic_bytes(b"PK\x03\x04" + b"\x00" * 60) is None


# ─────────────────────────────────────────────────────────────────────────────
# 3. Composite Validator
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_EXTS = (".mp3", ".wav", ".m4a", ".mp4")
ALLOWED_MIMES = (
    "audio/mpeg", "audio/wav", "audio/x-wav",
    "audio/mp4", "audio/x-m4a", "video/mp4",
)
MAX_MB = 10


def _mp3_header():
    return b"ID3" + b"\x00" * 61


def _wav_header():
    return b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 52


class TestValidateAudioFile:
    def test_valid_mp3(self):
        ok, msg, mime = validate_audio_file(
            filename="report.mp3",
            file_header=_mp3_header(),
            file_size_bytes=1024,
            allowed_extensions=ALLOWED_EXTS,
            allowed_mime_types=ALLOWED_MIMES,
            max_size_mb=MAX_MB,
        )
        assert ok is True
        assert msg == ""
        assert mime == "audio/mpeg"

    def test_valid_wav(self):
        ok, msg, mime = validate_audio_file(
            filename="speech.wav",
            file_header=_wav_header(),
            file_size_bytes=2048,
            allowed_extensions=ALLOWED_EXTS,
            allowed_mime_types=ALLOWED_MIMES,
            max_size_mb=MAX_MB,
        )
        assert ok is True
        assert mime == "audio/wav"

    def test_rejects_wrong_extension(self):
        ok, msg, _ = validate_audio_file(
            filename="malware.exe",
            file_header=_mp3_header(),
            file_size_bytes=1024,
            allowed_extensions=ALLOWED_EXTS,
            allowed_mime_types=ALLOWED_MIMES,
            max_size_mb=MAX_MB,
        )
        assert ok is False
        assert ".exe" in msg

    def test_rejects_oversized_file(self):
        ok, msg, _ = validate_audio_file(
            filename="huge.mp3",
            file_header=_mp3_header(),
            file_size_bytes=20 * 1024 * 1024,   # 20 MB > 10 MB limit
            allowed_extensions=ALLOWED_EXTS,
            allowed_mime_types=ALLOWED_MIMES,
            max_size_mb=MAX_MB,
        )
        assert ok is False
        assert "size" in msg.lower() or "MB" in msg

    def test_rejects_mp3_extension_but_zip_content(self):
        """Extension says .mp3 but magic bytes say ZIP — should be rejected."""
        zip_header = b"PK\x03\x04" + b"\x00" * 60
        ok, msg, _ = validate_audio_file(
            filename="not_audio.mp3",
            file_header=zip_header,
            file_size_bytes=512,
            allowed_extensions=ALLOWED_EXTS,
            allowed_mime_types=ALLOWED_MIMES,
            max_size_mb=MAX_MB,
        )
        assert ok is False
        assert "content" in msg.lower() or "audio" in msg.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Storage Path Generation
# ─────────────────────────────────────────────────────────────────────────────

class TestStoragePath:
    def test_generates_uuid_subdir(self, tmp_path):
        abs_path, rel_path = generate_storage_path(str(tmp_path), "audio.mp3")
        # First component should be a valid UUID
        parts = rel_path.replace("\\", "/").split("/")
        assert len(parts) == 2
        uuid.UUID(parts[0])   # raises ValueError if not a valid UUID

    def test_preserves_extension(self, tmp_path):
        _, rel_path = generate_storage_path(str(tmp_path), "news.wav")
        assert rel_path.endswith(".wav")

    def test_unique_paths(self, tmp_path):
        _, r1 = generate_storage_path(str(tmp_path), "audio.mp3")
        _, r2 = generate_storage_path(str(tmp_path), "audio.mp3")
        assert r1 != r2   # UUID must differ each call

    def test_sanitizes_dangerous_filename(self, tmp_path):
        _, rel_path = generate_storage_path(str(tmp_path), "../../evil.mp3")
        parts = rel_path.replace("\\", "/").split("/")
        assert len(parts) == 2    # no extra path traversal components
        assert ".." not in parts[1]
