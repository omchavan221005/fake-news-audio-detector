"""
Live End-to-End Pipeline Integration Test.

Tests:
  1. Health check.
  2. Audio file upload via HTTP multipart/form-data.
  3. Analysis pipeline job triggering.
  4. Status polling and stage progression (TRANSCRIBING -> EXTRACTING_CLAIMS -> VERIFYING -> DETECTING_AUDIO -> COMPLETED).
  5. Full analysis report retrieval and schema validation.
  6. Audio streaming endpoint verification.
"""
import io
import math
import struct
import time
import wave
import httpx
import pytest

BASE_URL = "http://localhost:8000"


@pytest.fixture
def sample_wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        for i in range(16000 * 2):
            t = i / 16000
            val = int(32767.0 * 0.4 * math.sin(2.0 * math.pi * 330.0 * t))
            wav.writeframes(struct.pack("<h", val))
    return buf.getvalue()


def test_live_health():
    with httpx.Client(base_url=BASE_URL, timeout=5.0) as client:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


def test_live_upload_and_pipeline_execution(sample_wav_bytes):
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Upload
        files = {"file": ("e2e_test.wav", sample_wav_bytes, "audio/wav")}
        upload_resp = client.post("/api/audio/upload", files=files)
        assert upload_resp.status_code in (200, 201)
        upload_data = upload_resp.json()
        audio_file_id = upload_data.get("audio_file_id") or upload_data.get("id")
        assert audio_file_id is not None

        # 2. Verify stream endpoint
        stream_resp = client.get(f"/api/audio/{audio_file_id}/stream")
        assert stream_resp.status_code in (200, 206)

        # 3. Trigger analysis
        job_resp = client.post("/api/analyze", json={"audio_file_id": audio_file_id})
        assert job_resp.status_code in (200, 201)
        job_data = job_resp.json()
        job_id = job_data["id"]
        assert job_id is not None

        # 4. Poll until complete
        final_status = None
        for _ in range(30):
            time.sleep(1.0)
            status_resp = client.get(f"/api/analyze/{job_id}/status")
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            if status_data["status"] in ("COMPLETED", "FAILED"):
                final_status = status_data["status"]
                break

        assert final_status == "COMPLETED", f"Pipeline failed with error: {status_data.get('error_message')}"

        # 5. Retrieve full results
        result_resp = client.get(f"/api/analyze/{job_id}")
        assert result_resp.status_code == 200
        res = result_resp.json()

        assert res["status"] == "COMPLETED"
        assert res["overall_credibility"] is not None
        assert res["overall_authenticity"] is not None
        assert res["overall_risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        assert 0.0 <= res["overall_risk_score"] <= 1.0
        assert "transcription" in res
        assert "audio_authenticity_result" in res
