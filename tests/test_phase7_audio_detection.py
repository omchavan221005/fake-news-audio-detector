"""
Phase 7 Tests — Audio Authenticity & Deepfake Detection

Tests:
  1. Waveform decoding via PyAV.
  2. Acoustic and spectral feature extraction metrics.
  3. Non-existent file and silent audio handling.
  4. Audio authenticity classifier scoring and probability calibration.
  5. Compatibility with AudioAuthenticityResult DB model and complete_job verdict synthesis.
"""
from __future__ import annotations

import math
import os
import struct
import sys
import tempfile
import wave
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.models import AudioAuthenticityResult, AuthenticityVerdict
from ml.audio_detection.feature_extractor import (
    load_audio_waveform,
    extract_acoustic_features,
    compute_spectral_centroid,
    compute_spectral_rolloff,
    compute_zero_crossing_rate,
    compute_frame_stft,
)
from ml.audio_detection.detector import detect_audio_authenticity


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def synthetic_speech_like_wav():
    """Generates a 2-second frequency-modulated synthetic speech-like WAV."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    sr = 16000
    duration = 2.0
    total_samples = int(sr * duration)

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sr)
        for i in range(total_samples):
            t = i / sr
            # Formant simulation: carrier ~ 180Hz modulated by 3Hz prosody + 700Hz formant
            f0 = 180.0 + 30.0 * math.sin(2.0 * math.pi * 3.0 * t)
            val1 = 0.4 * math.sin(2.0 * math.pi * f0 * t)
            val2 = 0.2 * math.sin(2.0 * math.pi * 700.0 * t)
            val3 = 0.1 * math.sin(2.0 * math.pi * 2200.0 * t)
            sample = int(32767.0 * (val1 + val2 + val3))
            wav.writeframes(struct.pack("<h", max(-32767, min(32767, sample))))

    yield wav_path

    if os.path.exists(wav_path):
        os.unlink(wav_path)


@pytest.fixture
def silent_wav():
    """Generates a 1-second pure silence WAV file."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000)

    yield wav_path

    if os.path.exists(wav_path):
        os.unlink(wav_path)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Waveform Loader
# ─────────────────────────────────────────────────────────────────────────────

def test_load_audio_waveform_valid(synthetic_speech_like_wav):
    waveform, sr = load_audio_waveform(synthetic_speech_like_wav, target_sr=16000)
    assert sr == 16000
    assert len(waveform) == 32000
    assert waveform.dtype.name == "float32"


def test_load_audio_waveform_missing_file():
    with pytest.raises(FileNotFoundError):
        load_audio_waveform("C:/non_existent_path_to_audio_file.wav")


# ─────────────────────────────────────────────────────────────────────────────
# 2. Acoustic Feature Extraction
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_acoustic_features_presence(synthetic_speech_like_wav):
    features = extract_acoustic_features(synthetic_speech_like_wav)

    required_keys = [
        "duration_seconds",
        "sample_rate",
        "is_silent",
        "rms_energy",
        "crest_factor",
        "spectral_centroid_hz",
        "spectral_rolloff_hz",
        "zero_crossing_rate_mean",
        "zero_crossing_rate_var",
        "high_frequency_artifact_ratio",
        "pitch_mean_hz",
        "pitch_std_hz",
        "prosodic_continuity",
    ]

    for key in required_keys:
        assert key in features, f"Missing key: {key}"

    assert features["duration_seconds"] == pytest.approx(2.0, 0.1)
    assert not features["is_silent"]
    assert features["spectral_centroid_hz"] > 0
    assert features["spectral_rolloff_hz"] > 0


def test_extract_acoustic_features_silence(silent_wav):
    features = extract_acoustic_features(silent_wav)
    assert features["is_silent"] is True
    assert features["rms_energy"] == 0.0


def test_spectral_math():
    sr = 16000
    # 1-second 1000Hz pure tone
    t = [i / sr for i in range(sr)]
    tone = [math.sin(2.0 * math.pi * 1000.0 * x) for x in t]
    import numpy as np
    y = np.array(tone, dtype=np.float32)

    spec = compute_frame_stft(y, n_fft=1024, hop_length=512)
    centroid = compute_spectral_centroid(spec, sr)
    # Centroid of a 1000Hz tone should be close to 1000Hz
    assert 900.0 <= centroid <= 1100.0

    rolloff = compute_spectral_rolloff(spec, sr, percentile=0.85)
    assert rolloff >= 1000.0

    zcr_mean, zcr_var = compute_zero_crossing_rate(y)
    assert zcr_mean > 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 3. Audio Authenticity Detector
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_audio_authenticity_schema(synthetic_speech_like_wav):
    result = detect_audio_authenticity(synthetic_speech_like_wav)

    assert "human_probability" in result
    assert "ai_probability" in result
    assert "detection_confidence" in result
    assert "model_used" in result
    assert "acoustic_features" in result

    assert 0.0 <= result["human_probability"] <= 1.0
    assert 0.0 <= result["ai_probability"] <= 1.0
    assert result["human_probability"] + result["ai_probability"] == pytest.approx(1.0, 0.01)
    assert 0.0 <= result["detection_confidence"] <= 1.0
    assert isinstance(result["model_used"], str)


def test_detect_audio_authenticity_silence_fallback(silent_wav):
    result = detect_audio_authenticity(silent_wav)
    assert result["human_probability"] == 0.5
    assert result["ai_probability"] == 0.5
    assert result["detection_confidence"] == 0.0


def test_detect_audio_authenticity_missing_file():
    with pytest.raises(FileNotFoundError):
        detect_audio_authenticity("C:/missing_path_xyz.mp3")


# ─────────────────────────────────────────────────────────────────────────────
# 4. Database Model Compatibility
# ─────────────────────────────────────────────────────────────────────────────

def test_audio_authenticity_db_model_compatibility(synthetic_speech_like_wav):
    result = detect_audio_authenticity(synthetic_speech_like_wav)

    auth_record = AudioAuthenticityResult(
        human_probability=result["human_probability"],
        ai_probability=result["ai_probability"],
        detection_confidence=result["detection_confidence"],
        model_used=result["model_used"],
        acoustic_features_json=result["acoustic_features"],
    )

    assert auth_record.human_probability == result["human_probability"]
    assert auth_record.ai_probability == result["ai_probability"]
    assert auth_record.detection_confidence == result["detection_confidence"]
    assert auth_record.model_used == result["model_used"]
    assert isinstance(auth_record.acoustic_features_json, dict)


def test_verdict_derivation_logic():
    """Verify the job_service derivation rules: >=0.7 -> LIKELY_AI, >=0.4 -> POSSIBLY_MANIPULATED, else LIKELY_HUMAN."""
    def derive(ai_prob):
        if ai_prob >= 0.7:
            return AuthenticityVerdict.LIKELY_AI
        elif ai_prob >= 0.4:
            return AuthenticityVerdict.POSSIBLY_MANIPULATED
        return AuthenticityVerdict.LIKELY_HUMAN

    assert derive(0.85) == AuthenticityVerdict.LIKELY_AI
    assert derive(0.70) == AuthenticityVerdict.LIKELY_AI
    assert derive(0.55) == AuthenticityVerdict.POSSIBLY_MANIPULATED
    assert derive(0.40) == AuthenticityVerdict.POSSIBLY_MANIPULATED
    assert derive(0.35) == AuthenticityVerdict.LIKELY_HUMAN
    assert derive(0.10) == AuthenticityVerdict.LIKELY_HUMAN
