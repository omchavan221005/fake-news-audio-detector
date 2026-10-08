"""
Speech-to-Text transcriber using faster-whisper with Silero-VAD.

Provides:
  - WhisperModelManager: Thread-safe singleton/cached model loader.
  - transcribe_audio: High-level transcription with VAD filtering and timestamps.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from faster_whisper import WhisperModel

from app.config import settings

logger = logging.getLogger("fnad.ml.stt")


class WhisperModelManager:
    """
    Thread-safe manager for WhisperModel instances.
    Caches loaded models so multiple transcription tasks share the same model in memory.
    """

    _lock = threading.Lock()
    _instances: dict[tuple[str, str, str], WhisperModel] = {}

    @classmethod
    def get_model(
        cls,
        model_size: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> WhisperModel:
        size = model_size or settings.whisper_model_size or "base"
        dev = device or settings.whisper_device or "cpu"
        comp = compute_type or settings.whisper_compute_type or "default"

        # Resolve auto device
        if dev == "auto":
            try:
                import torch
                dev = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                dev = "cpu"

        # Resolve default compute type
        if comp == "default":
            comp = "float16" if dev == "cuda" else "int8"

        cache_key = (size, dev, comp)

        with cls._lock:
            if cache_key not in cls._instances:
                logger.info(
                    "Loading faster-whisper model: size=%s, device=%s, compute_type=%s...",
                    size, dev, comp
                )
                start_t = time.time()
                try:
                    model = WhisperModel(
                        model_size_or_path=size,
                        device=dev,
                        compute_type=comp,
                    )
                except Exception as exc:
                    logger.warning("Default Whisper download/load failed (%s). Searching local cache...", exc)
                    # Search local huggingface cache snapshots directly
                    from pathlib import Path
                    hub_dir = Path.home() / ".cache" / "huggingface" / "hub"
                    candidates = [
                        hub_dir / f"models--Systran--faster-whisper-{size}",
                        hub_dir / "models--Systran--faster-whisper-base",
                        hub_dir / "models--Systran--faster-whisper-tiny",
                    ]
                    found_path = None
                    for c in candidates:
                        snaps = c / "snapshots"
                        if snaps.exists():
                            for s in snaps.iterdir():
                                if (s / "model.bin").exists() and (s / "config.json").exists():
                                    found_path = str(s)
                                    break
                        if found_path:
                            break

                    if found_path:
                        logger.info("Found cached snapshot at %s; loading directly...", found_path)
                        model = WhisperModel(
                            model_size_or_path=found_path,
                            device=dev,
                            compute_type=comp,
                        )
                    else:
                        raise exc

                cls._instances[cache_key] = model
                logger.info(
                    "Model %s loaded successfully in %.2fs",
                    size, time.time() - start_t
                )
            return cls._instances[cache_key]

    @classmethod
    def unload_all(cls) -> None:
        """Unload and clear all cached models from memory."""
        with cls._lock:
            cls._instances.clear()
            logger.info("All cached Whisper models unloaded.")


def transcribe_audio(
    audio_path: str,
    model_size: str | None = None,
    device: str | None = None,
    compute_type: str | None = None,
    beam_size: int = 5,
    word_timestamps: bool = True,
    vad_filter: bool = True,
) -> dict[str, Any]:
    """
    Transcribe an audio file using faster-whisper with Silero-VAD silence filtering.

    Parameters:
        audio_path: Path to the audio file (.mp3, .wav, .m4a, .mp4, etc.)
        model_size: Model size override ('tiny', 'base', 'small', 'medium', 'large-v3')
        device: 'cpu' | 'cuda' | 'auto'
        compute_type: 'int8' | 'float16' | 'float32' | 'default'
        beam_size: Beam search width (default: 5)
        word_timestamps: Whether to extract word-level timestamps
        vad_filter: Whether to use Silero VAD to suppress silence/noise

    Returns:
        {
          "full_text": str,
          "language": str,
          "language_prob": float,
          "duration": float,
          "segments": [
            {
              "id": int,
              "start": float,
              "end": float,
              "text": str,
              "words": [
                {"word": str, "start": float, "end": float, "probability": float},
                ...
              ]
            },
            ...
          ]
        }
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    start_time = time.time()
    logger.info("Starting transcription for: %s", audio_path)

    model = WhisperModelManager.get_model(
        model_size=model_size,
        device=device,
        compute_type=compute_type,
    )

    vad_params = dict(
        min_silence_duration_ms=500,
        speech_pad_ms=200,
    ) if vad_filter else None

    try:
        segments_gen, info = model.transcribe(
            audio_path,
            beam_size=beam_size,
            word_timestamps=word_timestamps,
            vad_filter=vad_filter,
            vad_parameters=vad_params,
        )

        detected_lang = getattr(info, "language", "unknown")
        lang_prob = float(getattr(info, "language_probability", 0.0))
        duration = float(getattr(info, "duration", 0.0))

        segments_list = []
        text_chunks = []

        for seg in segments_gen:
            seg_text = seg.text.strip()
            if not seg_text:
                continue

            text_chunks.append(seg_text)

            words_data = []
            if word_timestamps and getattr(seg, "words", None):
                for w in seg.words:
                    words_data.append({
                        "word": w.word,
                        "start": round(float(w.start), 2),
                        "end": round(float(w.end), 2),
                        "probability": round(float(w.probability), 3),
                    })

            segments_list.append({
                "id": seg.id,
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
                "text": seg_text,
                "words": words_data,
            })

    except ValueError as val_err:
        # Silero VAD filtered out 100% of frames because no human speech was detected
        logger.warning(
            "No speech detected by VAD in %s (faster-whisper notice: %s)",
            audio_path, val_err
        )
        return {
            "full_text": "",
            "language": "unknown",
            "language_prob": 0.0,
            "duration": 0.0,
            "segments": [],
        }

    full_text = " ".join(text_chunks).strip()
    elapsed = time.time() - start_time

    logger.info(
        "Transcription complete for %s in %.2fs (lang=%s, prob=%.2f, %d segments, %d chars)",
        audio_path, elapsed, detected_lang, lang_prob, len(segments_list), len(full_text)
    )

    return {
        "full_text": full_text,
        "language": detected_lang,
        "language_prob": lang_prob,
        "duration": duration,
        "segments": segments_list,
    }
