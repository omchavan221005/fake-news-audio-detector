# 🎙️ Fake News Detection from Audio

> **Multimodal Audio Verification System**: Audio Ingestion ➔ Faster-Whisper STT ➔ Claim Extraction ➔ Live Web/Wikipedia Fact Verification ➔ Acoustic Deepfake Forensics ➔ Interactive Glassmorphic React Dashboard.

---

## 🌟 Overview

The **Fake News Audio Detector** is an end-to-end multimodal artificial intelligence application designed to analyze spoken audio recordings (news clips, interviews, speeches, social media broadcasts, voice notes) across two distinct dimensions:

1. **Content Credibility (Semantic / Fact-Checking)**:
   - High-fidelity Speech-to-Text transcription with word-level timestamps and Silero VAD silence rejection.
   - Check-worthiness filtering and factual claim extraction.
   - Live evidence retrieval (Wikipedia API zero-key fallback + Serper/Google & Tavily API integration).
   - Natural Language Inference (NLI) stance analysis classifying evidence as *Supports*, *Contradicts*, or *Neutral*.
   - Overall credibility synthesis: **Credible**, **Misleading**, **False**, or **Unverified**.

2. **Audio Authenticity (Acoustic Forensics / Deepfake Detection)**:
   - Waveform decoding and spectral acoustic feature extraction (PyAV / SciPy / NumPy).
   - Pitch contour and prosodic variance analysis (detecting unnatural monotonic synthesized pitch).
   - Vocoder artifact indexing & zero-crossing / dynamic range analysis.
   - Authenticity synthesis: **Human-Generated**, **AI-Generated / Synthetic**, or **Possibly Manipulated**.

---

## 🏗️ Architecture

```mermaid
graph TD
    A[User Audio Upload (.mp3, .wav, .m4a, .mp4)] --> B[Magic-Byte Security Validation & Storage]
    B --> C[Background Worker Pipeline]
    
    subgraph "Multimodal Analysis Engine"
        C --> D[1. Speech-to-Text: faster-whisper + Silero VAD]
        D --> E[2. Factual Claim Extraction & Timestamp Alignment]
        E --> F[3. Evidence Retrieval: Serper / Tavily / Wikipedia]
        F --> G[4. NLI Stance Analysis & Credibility Synthesis]
        
        C --> H[5. Acoustic Forensics & Deepfake Detection]
        H --> I[Spectral Rolloff / Centroid / Pitch F0 / Vocoder Index]
    end

    G --> J[Unified Synthesis Engine & Risk Scoring]
    I --> J
    J --> K[Real-time Polling API]
    K --> L[Glassmorphic React 18 Dashboard]
```

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.12)
- **Node.js 18+** & `npm`
- *(Optional)* PostgreSQL (Defaults to built-in local SQLite if PostgreSQL is not running)

### 2. Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Start FastAPI server (runs at http://localhost:8000)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
```bash
# In a new terminal, navigate to frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite development server (runs at http://localhost:5173)
npm run dev
```

Visit **`http://localhost:5173`** in your web browser.

---

## 🧪 Running Automated Tests

The test suite includes **90 comprehensive unit and end-to-end integration tests**:

```bash
# Run the entire test suite
pytest tests/ -v
```

### Test Coverage Breakdown
- `test_phase3_audio_upload.py` (24 tests): Magic-byte MIME validation, secure UUID paths, HTTP Range streaming.
- `test_phase4_transcription.py` (8 tests): Whisper model manager caching, VAD silence trimming, timestamped segments.
- `test_phase5_claim_extraction.py` (22 tests): Sentence boundary detection, check-worthiness filtering, timestamp mapping.
- `test_phase6_claim_verification.py` (24 tests): Domain credibility scoring, search query generation, NLI stance scoring, credibility synthesis.
- `test_phase7_audio_detection.py` (10 tests): PyAV waveform decoding, spectral rolloff/centroid math, pitch variance, synthetic classification.
- `test_live_e2e_pipeline.py` (2 tests): Live end-to-end upload and analysis pipeline verification.

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` or `/api/health` | Liveness check & active configuration |
| `POST` | `/api/audio/upload` | Upload audio file (`.mp3`, `.wav`, `.m4a`, `.mp4`) |
| `GET` | `/api/audio/{id}/stream` | Stream audio with HTTP 206 partial content range support |
| `POST` | `/api/analyze` | Dispatch background analysis job for an uploaded audio file |
| `GET` | `/api/analyze/{job_id}/status` | Live polling endpoint for job progress percentage and current stage |
| `GET` | `/api/analyze/{job_id}` | Retrieve comprehensive multimodal analysis report |

---

## 🎨 Interactive Dashboard Features

- **Drag-and-Drop Uploader**: Real-time magic-byte verification, file size checks, and instant upload progress.
- **Synchronized Audio Player**: Custom waveform-inspired player with timestamp synchronization. Clicking any claim or transcript segment jumps audio directly to that exact second.
- **Multimodal Verdict Banner**: High-visibility glassmorphic badge showing synthesized credibility, acoustic authenticity, and calibrated risk score.
- **Filterable Claims Explorer**: Filter claims by *True*, *False*, *Misleading*, or *Unverified* with expandable evidence citations, publisher credibility badges, and direct source links.
- **Acoustic Forensics Radar**: Visual gauges for Spectral Rolloff, RMS Dynamic Range, Pitch Contours, and Vocoder Artifact Index.

---

## 🛠️ Environment Configuration (`.env`)

```ini
# Application Environment
ENVIRONMENT=development
DATABASE_URL=sqlite:///./data/fnad.db

# Whisper ASR Configuration
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Search API Provider (serper | tavily | wikipedia)
SEARCH_API_PROVIDER=wikipedia
SEARCH_API_KEY=

# Audio Storage
AUDIO_STORAGE_PATH=./data/audio
MAX_UPLOAD_SIZE_MB=50
```
