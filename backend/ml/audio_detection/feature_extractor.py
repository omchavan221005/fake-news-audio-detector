"""
Acoustic and Spectral Feature Extraction for Audio Deepfake Forensics.

Decodes input audio files to standardized 16kHz mono float32 waveforms using PyAV
and extracts spectral, prosodic, and temporal acoustic signatures.
"""
from __future__ import annotations

import logging
import math
import os
from typing import Any

import av
import numpy as np

logger = logging.getLogger("fnad.ml.audio_features")

DEFAULT_SAMPLE_RATE = 16000


def load_audio_waveform(audio_path: str, target_sr: int = DEFAULT_SAMPLE_RATE) -> tuple[np.ndarray, int]:
    """
    Decode an audio file (.mp3, .wav, .m4a, .mp4, etc.) to a 1D float32 numpy array
    resampled to target_sr using PyAV.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    container = av.open(audio_path)
    if not container.streams.audio:
        container.close()
        raise ValueError(f"No audio stream found in: {audio_path}")

    stream = container.streams.audio[0]
    resampler = av.AudioResampler(format="flt", layout="mono", rate=target_sr)

    frames: list[np.ndarray] = []
    for frame in container.decode(stream):
        for resampled_frame in resampler.resample(frame):
            frames.append(resampled_frame.to_ndarray())

    container.close()

    if not frames:
        return np.array([], dtype=np.float32), target_sr

    waveform = np.concatenate(frames, axis=1).flatten()
    return waveform, target_sr


def compute_frame_stft(
    y: np.ndarray,
    n_fft: int = 1024,
    hop_length: int = 512,
) -> np.ndarray:
    """Compute magnitude spectrogram using short-time Fourier transform with Hann window."""
    if len(y) < n_fft:
        pad_width = n_fft - len(y)
        y = np.pad(y, (0, pad_width), mode="constant")

    window = np.hanning(n_fft)
    num_frames = 1 + (len(y) - n_fft) // hop_length
    frames = np.lib.stride_tricks.as_strided(
        y,
        shape=(num_frames, n_fft),
        strides=(y.strides[0] * hop_length, y.strides[0]),
    )
    windowed = frames * window
    spectrogram = np.abs(np.fft.rfft(windowed, n=n_fft))
    return spectrogram


def compute_spectral_centroid(mag_spec: np.ndarray, sr: int = DEFAULT_SAMPLE_RATE) -> float:
    """Compute mean spectral centroid in Hz across all frames."""
    n_bins = mag_spec.shape[1]
    freqs = np.linspace(0, sr / 2, n_bins)
    magnitudes = mag_spec + 1e-10

    centroids = np.sum(magnitudes * freqs, axis=1) / np.sum(magnitudes, axis=1)
    return float(np.mean(centroids))


def compute_spectral_rolloff(
    mag_spec: np.ndarray,
    sr: int = DEFAULT_SAMPLE_RATE,
    percentile: float = 0.85,
) -> float:
    """Compute frequency below which percentile (e.g. 85%) of spectral energy lies."""
    n_bins = mag_spec.shape[1]
    freqs = np.linspace(0, sr / 2, n_bins)
    total_energy = np.sum(mag_spec, axis=1, keepdims=True) + 1e-10
    cumulative_energy = np.cumsum(mag_spec, axis=1)

    threshold = percentile * total_energy
    rolloff_indices = np.argmax(cumulative_energy >= threshold, axis=1)
    rolloff_freqs = freqs[rolloff_indices]
    return float(np.mean(rolloff_freqs))


def compute_zero_crossing_rate(y: np.ndarray, frame_size: int = 1024, hop_length: int = 512) -> tuple[float, float]:
    """Compute mean and variance of zero-crossing rate across sliding frames."""
    if len(y) < frame_size:
        return 0.0, 0.0

    num_frames = 1 + (len(y) - frame_size) // hop_length
    zcrs = []
    for i in range(num_frames):
        frame = y[i * hop_length : i * hop_length + frame_size]
        zcr = np.mean(np.abs(np.diff(np.sign(frame)))) / 2.0
        zcrs.append(zcr)

    if not zcrs:
        return 0.0, 0.0
    return float(np.mean(zcrs)), float(np.var(zcrs))


def compute_rms_and_crest_factor(y: np.ndarray) -> tuple[float, float]:
    """Compute root-mean-square energy (RMS) and crest factor (peak to RMS ratio)."""
    if len(y) == 0:
        return 0.0, 0.0
    rms = float(np.sqrt(np.mean(y ** 2)))
    if rms < 1e-7:
        return 0.0, 0.0
    peak = float(np.max(np.abs(y)))
    crest_factor = float(peak / rms)
    return rms, crest_factor


def compute_high_frequency_artifact_ratio(
    mag_spec: np.ndarray,
    sr: int = DEFAULT_SAMPLE_RATE,
    cutoff_hz: float = 6500.0,
) -> float:
    """
    Measure ratio of energy in upper frequency band (> 6.5kHz) relative to total energy.
    Many neural vocoders show either distinct drop-offs or abnormal phase noise in this band.
    """
    n_bins = mag_spec.shape[1]
    freqs = np.linspace(0, sr / 2, n_bins)
    hf_mask = freqs >= cutoff_hz

    hf_energy = np.sum(mag_spec[:, hf_mask])
    total_energy = np.sum(mag_spec) + 1e-10
    return float(hf_energy / total_energy)


def compute_pitch_and_prosody(
    y: np.ndarray,
    sr: int = DEFAULT_SAMPLE_RATE,
    frame_size: int = 1024,
    hop_length: int = 512,
) -> tuple[float, float, float]:
    """
    Estimate fundamental frequency (F0) using autocorrelation across frames.
    Returns: (mean_f0_hz, f0_std_dev, f0_continuity_ratio)
    """
    if len(y) < frame_size:
        return 0.0, 0.0, 0.0

    min_period = int(sr / 400)  # max pitch 400 Hz
    max_period = int(sr / 60)   # min pitch 60 Hz

    num_frames = 1 + (len(y) - frame_size) // hop_length
    pitches: list[float] = []

    for i in range(num_frames):
        frame = y[i * hop_length : i * hop_length + frame_size]
        # Skip low energy silence frames
        if np.max(np.abs(frame)) < 0.01:
            continue

        autocorr = np.correlate(frame, frame, mode="full")
        autocorr = autocorr[len(frame) - 1 :]

        if len(autocorr) > max_period:
            search_window = autocorr[min_period:max_period]
            if len(search_window) > 0 and np.max(search_window) > 0.35 * autocorr[0]:
                peak_idx = np.argmax(search_window) + min_period
                f0 = sr / peak_idx
                pitches.append(f0)

    if len(pitches) < 3:
        return 0.0, 0.0, 0.0

    mean_f0 = float(np.mean(pitches))
    std_f0 = float(np.std(pitches))
    continuity = float(len(pitches) / max(1, num_frames))

    return mean_f0, std_f0, continuity


def compute_temporal_timeline(
    waveform: np.ndarray,
    sr: int,
    window_sec: float = 1.5,
    hop_sec: float = 1.0,
) -> list[dict[str, Any]]:
    """
    Divide audio into overlapping temporal slices and compute localized acoustic consistency
    to detect voice splicing or localized deepfake segments.
    """
    win_len = int(window_sec * sr)
    hop_len = int(hop_sec * sr)
    total_len = len(waveform)
    
    if total_len < win_len:
        return []

    segments: list[dict[str, Any]] = []
    for start_idx in range(0, total_len - win_len + 1, hop_len):
        end_idx = start_idx + win_len
        chunk = waveform[start_idx:end_idx]
        
        start_time = round(start_idx / sr, 2)
        end_time = round(end_idx / sr, 2)
        
        rms, _ = compute_rms_and_crest_factor(chunk)
        if rms < 0.002:
            segments.append({
                "start": start_time,
                "end": end_time,
                "is_speech": False,
                "ai_score": 0.5,
                "spectral_rolloff": 0.0,
            })
            continue

        stft_chunk = compute_frame_stft(chunk)
        rolloff = compute_spectral_rolloff(stft_chunk, sr)
        _, pitch_std, _ = compute_pitch_and_prosody(chunk, sr)
        hf_art = compute_high_frequency_artifact_ratio(stft_chunk, sr)

        # Local AI probability heuristic
        ai_p = 0.5
        if pitch_std < 6.0 and pitch_std > 0:
            ai_p += 0.25
        if rolloff < 2200 or rolloff > 7400:
            ai_p += 0.15
        if hf_art > 0.08:
            ai_p += 0.15
        if 14.0 <= pitch_std <= 50.0 and 2800 <= rolloff <= 5800:
            ai_p -= 0.30

        ai_p = float(np.clip(ai_p, 0.05, 0.95))

        segments.append({
            "start": start_time,
            "end": end_time,
            "is_speech": True,
            "ai_score": round(ai_p, 3),
            "spectral_rolloff": round(rolloff, 1),
            "pitch_std": round(pitch_std, 1),
        })

    return segments


def extract_acoustic_features(audio_path: str) -> dict[str, Any]:
    """
    Extract a comprehensive suite of acoustic metrics for deepfake detection.
    """
    waveform, sr = load_audio_waveform(audio_path)

    duration_sec = float(len(waveform) / sr) if len(waveform) > 0 else 0.0
    if len(waveform) < 1024:
        # Audio too short or empty
        return {
            "duration_seconds": duration_sec,
            "sample_rate": sr,
            "is_silent": True,
            "rms_energy": 0.0,
            "crest_factor": 0.0,
            "spectral_centroid_hz": 0.0,
            "spectral_rolloff_hz": 0.0,
            "zero_crossing_rate_mean": 0.0,
            "zero_crossing_rate_var": 0.0,
            "high_frequency_artifact_ratio": 0.0,
            "pitch_mean_hz": 0.0,
            "pitch_std_hz": 0.0,
            "prosodic_continuity": 0.0,
            "temporal_segments": [],
        }

    rms, crest_factor = compute_rms_and_crest_factor(waveform)
    is_silent = rms < 0.002

    mag_spec = compute_frame_stft(waveform)
    centroid = compute_spectral_centroid(mag_spec, sr)
    rolloff = compute_spectral_rolloff(mag_spec, sr)
    zcr_mean, zcr_var = compute_zero_crossing_rate(waveform)
    hf_ratio = compute_high_frequency_artifact_ratio(mag_spec, sr)
    pitch_mean, pitch_std, continuity = compute_pitch_and_prosody(waveform, sr)
    temporal_segments = compute_temporal_timeline(waveform, sr)

    return {
        "duration_seconds": round(duration_sec, 2),
        "sample_rate": sr,
        "is_silent": is_silent,
        "rms_energy": round(rms, 4),
        "crest_factor": round(crest_factor, 2),
        "spectral_centroid_hz": round(centroid, 1),
        "spectral_rolloff_hz": round(rolloff, 1),
        "zero_crossing_rate_mean": round(zcr_mean, 4),
        "zero_crossing_rate_var": round(zcr_var, 6),
        "high_frequency_artifact_ratio": round(hf_ratio, 4),
        "pitch_mean_hz": round(pitch_mean, 1),
        "pitch_std_hz": round(pitch_std, 1),
        "prosodic_continuity": round(continuity, 3),
        "temporal_segments": temporal_segments,
    }
