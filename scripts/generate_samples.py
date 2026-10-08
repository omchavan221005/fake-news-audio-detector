"""
Utility script to generate synthetic test audio samples for the Fake News Detection pipeline.
"""
from __future__ import annotations

import math
import struct
import wave
from pathlib import Path


def generate_sample_audio():
    sample_dir = Path("data/sample_audio")
    sample_dir.mkdir(parents=True, exist_ok=True)

    sr = 16000

    # 1. Harmonic simulated speech tone
    speech_path = sample_dir / "sample_speech_tone.wav"
    with wave.open(str(speech_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(sr * 4.0)):
            t = i / sr
            f0 = 160 + 35 * math.sin(2 * math.pi * 1.2 * t)
            val = 0.5 * math.sin(2 * math.pi * f0 * t) + 0.25 * math.sin(2 * math.pi * 2 * f0 * t)
            int_val = int(max(-32767, min(32767, val * 32767)))
            frames.extend(struct.pack("<h", int_val))
        wf.writeframes(frames)

    # 2. Robotic flat pitch (synthetic vocoder-like tone)
    synth_path = sample_dir / "sample_flat_vocoder.wav"
    with wave.open(str(synth_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        frames = bytearray()
        for i in range(int(sr * 4.0)):
            t = i / sr
            f0 = 200.0  # Perfect flat pitch, no prosodic variance
            val = 0.6 * math.sin(2 * math.pi * f0 * t) + 0.3 * math.sin(2 * math.pi * 3 * f0 * t)
            int_val = int(max(-32767, min(32767, val * 32767)))
            frames.extend(struct.pack("<h", int_val))
        wf.writeframes(frames)

    print(f"Generated samples successfully in {sample_dir.resolve()}")


if __name__ == "__main__":
    generate_sample_audio()
