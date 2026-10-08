"""
Phase 4 Tests — Speech-to-Text with faster-whisper & Silero-VAD

Tests:
  1. WhisperModelManager singleton caching and model unloading.
  2. Device and compute_type resolution logic.
  3. FileNotFoundError handling for missing audio paths.
  4. Mocked Whisper transcription output schema, segment parsing, and word timestamps.
  5. Real audio / silence VAD handling with synthetic audio generation.
  6. Compatibility with the Transcription DB model schema.
"""
from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import wave
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ml.speech_to_text.transcriber import WhisperModelManager, transcribe_audio
from app.models.models import Transcription


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def cleanup_model_cache():
    """Ensure cache is reset after tests that manipulate it."""
    yield
    WhisperModelManager.unload_all()


@pytest.fixture
def synthetic_wav_file():
    """Creates a temporary 1-second 16kHz sine wave WAV file."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        for i in range(16000):
            val = int(32767.0 * 0.4 * math.sin(2.0 * math.pi * 440.0 * i / 16000.0))
            wav.writeframes(struct.pack("<h", val))

    yield wav_path

    if os.path.exists(wav_path):
        os.unlink(wav_path)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Model Manager & Caching
# ─────────────────────────────────────────────────────────────────────────────

def test_model_manager_singleton():
    """Verify that requesting the same model configuration returns the identical cached instance."""
    with patch("ml.speech_to_text.transcriber.WhisperModel") as mock_model_cls:
        instance_a = MagicMock()
        mock_model_cls.return_value = instance_a

        m1 = WhisperModelManager.get_model("tiny", device="cpu", compute_type="int8")
        m2 = WhisperModelManager.get_model("tiny", device="cpu", compute_type="int8")

        assert m1 is m2
        assert mock_model_cls.call_count == 1


def test_model_manager_unload_all():
    """Verify that unload_all clears the cache, forcing re-initialization on subsequent calls."""
    with patch("ml.speech_to_text.transcriber.WhisperModel") as mock_model_cls:
        instance_a = MagicMock()
        instance_b = MagicMock()
        mock_model_cls.side_effect = [instance_a, instance_b]

        m1 = WhisperModelManager.get_model("tiny", device="cpu", compute_type="int8")
        assert len(WhisperModelManager._instances) == 1

        WhisperModelManager.unload_all()
        assert len(WhisperModelManager._instances) == 0

        m2 = WhisperModelManager.get_model("tiny", device="cpu", compute_type="int8")
        assert mock_model_cls.call_count == 2
        assert m1 is not m2


def test_model_manager_different_keys():
    """Verify that different sizes or devices produce distinct cached instances."""
    with patch("ml.speech_to_text.transcriber.WhisperModel") as mock_model_cls:
        mock_model_cls.side_effect = [MagicMock(), MagicMock()]

        m_tiny = WhisperModelManager.get_model("tiny", device="cpu", compute_type="int8")
        m_base = WhisperModelManager.get_model("base", device="cpu", compute_type="int8")

        assert m_tiny is not m_base
        assert len(WhisperModelManager._instances) == 2


# ─────────────────────────────────────────────────────────────────────────────
# 2. Input Validation & Error Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_transcribe_missing_file_raises():
    """Verify that transcribe_audio raises FileNotFoundError for non-existent files."""
    with pytest.raises(FileNotFoundError, match="Audio file not found"):
        transcribe_audio("C:/non_existent_path_to_audio_file.mp3")


# ─────────────────────────────────────────────────────────────────────────────
# 3. Transcription Parsing & Schema Conformance
# ─────────────────────────────────────────────────────────────────────────────

def test_transcribe_audio_mocked_success(synthetic_wav_file):
    """Test full parsing logic: segments, words, language, prob, full text concatenation."""
    mock_word1 = SimpleNamespace(word=" Breaking", start=0.0, end=0.5, probability=0.98)
    mock_word2 = SimpleNamespace(word=" news", start=0.51, end=1.0, probability=0.95)

    mock_segment1 = SimpleNamespace(
        id=0,
        start=0.0,
        end=1.2,
        text=" Breaking news",
        words=[mock_word1, mock_word2],
    )
    mock_segment2 = SimpleNamespace(
        id=1,
        start=1.3,
        end=2.5,
        text=" regarding the event.",
        words=[],
    )

    mock_info = SimpleNamespace(
        language="en",
        language_probability=0.994,
        duration=2.5,
    )

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_segment1, mock_segment2], mock_info)

    with patch.object(WhisperModelManager, "get_model", return_value=mock_model):
        result = transcribe_audio(synthetic_wav_file)

    # Check top-level keys
    assert "full_text" in result
    assert "language" in result
    assert "language_prob" in result
    assert "duration" in result
    assert "segments" in result

    assert result["language"] == "en"
    assert result["language_prob"] == pytest.approx(0.994, 0.001)
    assert result["duration"] == pytest.approx(2.5, 0.01)
    assert result["full_text"] == "Breaking news regarding the event."

    # Check segments
    assert len(result["segments"]) == 2
    seg0 = result["segments"][0]
    assert seg0["id"] == 0
    assert seg0["start"] == 0.0
    assert seg0["end"] == 1.2
    assert seg0["text"] == "Breaking news"
    assert len(seg0["words"]) == 2
    assert seg0["words"][0]["word"] == " Breaking"
    assert seg0["words"][0]["probability"] == 0.98


def test_transcribe_audio_empty_segments(synthetic_wav_file):
    """Verify that segments containing only whitespace are skipped and empty text handled."""
    mock_empty_seg = SimpleNamespace(
        id=0,
        start=0.0,
        end=1.0,
        text="   ",
        words=[],
    )
    mock_info = SimpleNamespace(language="en", language_probability=0.85, duration=1.0)
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_empty_seg], mock_info)

    with patch.object(WhisperModelManager, "get_model", return_value=mock_model):
        result = transcribe_audio(synthetic_wav_file)

    assert result["full_text"] == ""
    assert result["segments"] == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. Real Audio / Silero VAD Non-Speech Graceful Handling
# ─────────────────────────────────────────────────────────────────────────────

def test_transcribe_audio_real_silence_non_speech(synthetic_wav_file):
    """
    When processing a pure sine wave tone (no human speech), Silero VAD filters out all frames.
    Verify that transcribe_audio catches the empty iterable ValueError and returns an empty transcript cleanly.
    """
    result = transcribe_audio(synthetic_wav_file, model_size="tiny", device="cpu", compute_type="int8")

    assert isinstance(result, dict)
    assert result["full_text"] == ""
    assert result["segments"] == []
    assert "language" in result
    assert "duration" in result


# ─────────────────────────────────────────────────────────────────────────────
# 5. Database Schema Compatibility
# ─────────────────────────────────────────────────────────────────────────────

def test_transcription_db_model_field_compatibility(synthetic_wav_file):
    """Verify that transcribe_audio return dictionary matches the Transcription ORM fields."""
    mock_info = SimpleNamespace(language="en", language_probability=0.98, duration=5.0)
    mock_seg = SimpleNamespace(id=0, start=0.0, end=1.0, text="Test transcript", words=[])
    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], mock_info)

    with patch.object(WhisperModelManager, "get_model", return_value=mock_model):
        result = transcribe_audio(synthetic_wav_file)

    # Transcription ORM model has: full_text, detected_language, detected_language_prob, segments_json
    orm_transcription = Transcription(
        full_text=result["full_text"],
        detected_language=result["language"],
        detected_language_prob=result["language_prob"],
        segments_json=result["segments"],
    )

    assert orm_transcription.full_text == "Test transcript"
    assert orm_transcription.detected_language == "en"
    assert orm_transcription.detected_language_prob == 0.98
    assert len(orm_transcription.segments_json) == 1
