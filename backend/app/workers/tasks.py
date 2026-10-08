"""
Background pipeline orchestrator.

This module wires together all ML stages into a single pipeline function
that runs inside the thread-pool worker (no external broker needed).

Stage sequence and approximate progress percentages:
  10% — TRANSCRIBING          (faster-whisper ASR)
  40% — EXTRACTING_CLAIMS     (NLP claim filter)
  70% — VERIFYING             (DeBERTa NLI + evidence retrieval)
  90% — DETECTING_AUDIO       (audio deepfake detector)
 100% — COMPLETED             (verdict synthesis)

Each stage updates job.status + job.progress_percent in PostgreSQL so the
frontend can poll /api/analyze/{job_id}/status and show a live progress bar.

Phases 4-7 will replace the stub ML calls with real model inference.
"""
from __future__ import annotations

import logging
import traceback
import uuid

from app.database import SessionLocal
from app.models.models import JobStatus, SourceType, Stance, AuthenticityVerdict
from app.services.job_service import advance_job, fail_job, complete_job

logger = logging.getLogger("fnad.tasks")


def run_analysis_pipeline(job_id: str) -> None:
    """
    Top-level pipeline runner invoked by the thread-pool worker.

    Each ML stage is imported lazily so that heavy models are loaded only
    when the worker actually processes a job — not at import time.
    """
    db = SessionLocal()
    try:
        _run(job_id, db)
    except Exception as exc:
        logger.error("Pipeline crashed for job %s:\n%s", job_id, traceback.format_exc())
        try:
            fail_job(uuid.UUID(job_id), db, str(exc))
        except Exception:
            pass
    finally:
        db.close()


def _run(job_id: str, db) -> None:
    uid = uuid.UUID(job_id)

    # ── Stage 1: Speech-to-Text ───────────────────────────────────────────────
    advance_job(uid, db, status=JobStatus.TRANSCRIBING, progress_percent=5,
                current_stage="Extracting speech from audio…")

    from app.models.models import AnalysisJob, Transcription
    from app.services.audio_service import resolve_storage_path

    job = db.query(AnalysisJob).filter(AnalysisJob.id == uid).first()
    if not job:
        raise RuntimeError(f"Job {job_id} not found in DB")

    audio_path = resolve_storage_path(job.audio_file.storage_path)

    # Phase 4 will replace this with real faster-whisper inference
    from ml.speech_to_text.transcriber import transcribe_audio
    transcript = transcribe_audio(audio_path)

    transcription = Transcription(
        job_id=uid,
        full_text=transcript["full_text"],
        detected_language=transcript["language"],
        detected_language_prob=transcript["language_prob"],
        segments_json=transcript["segments"],
    )
    db.add(transcription)
    db.commit()

    advance_job(uid, db, status=JobStatus.TRANSCRIBING, progress_percent=30,
                current_stage="Speech extracted successfully")

    # ── Stage 2: Claim Extraction ─────────────────────────────────────────────
    advance_job(uid, db, status=JobStatus.EXTRACTING_CLAIMS, progress_percent=35,
                current_stage="Identifying factual claims…")

    from ml.claim_extraction.extractor import extract_claims
    from app.models.models import Claim

    raw_claims = extract_claims(transcript["full_text"], transcript["segments"])

    claim_records = []
    for i, cl in enumerate(raw_claims):
        claim_rec = Claim(
            job_id=uid,
            claim_text=cl["text"],
            order_index=i,
            start_time=cl.get("start_time"),
            end_time=cl.get("end_time"),
        )
        db.add(claim_rec)
        claim_records.append(claim_rec)
    db.commit()
    for c in claim_records:
        db.refresh(c)

    advance_job(uid, db, status=JobStatus.EXTRACTING_CLAIMS, progress_percent=45,
                current_stage=f"Identified {len(claim_records)} verifiable claim(s)")

    # ── Stage 3: Claim Verification ───────────────────────────────────────────
    advance_job(uid, db, status=JobStatus.VERIFYING, progress_percent=50,
                current_stage="Retrieving evidence and verifying claims…")

    from ml.claim_verification.verifier import verify_claims
    from app.models.models import ClaimVerification, EvidenceSource

    verification_results = verify_claims([c.claim_text for c in claim_records])

    for claim_rec, vr in zip(claim_records, verification_results):
        cv = ClaimVerification(
            claim_id=claim_rec.id,
            classification=vr["classification"],
            confidence=vr["confidence"],
            explanation=vr["explanation"],
        )
        db.add(cv)
        db.flush()

        for src in vr.get("sources", []):
            es = EvidenceSource(
                claim_verification_id=cv.id,
                source_title=src.get("title"),
                source_url=src["url"],
                source_domain=src.get("domain"),
                source_type=SourceType(src.get("source_type", "other")) if isinstance(src.get("source_type"), str) else src.get("source_type", SourceType.OTHER),
                domain_credibility_score=src.get("credibility_score"),
                stance=Stance(src.get("stance", "neutral")) if isinstance(src.get("stance"), str) else src.get("stance", Stance.NEUTRAL),
                publication_date=src.get("publication_date"),
                excerpt=src.get("excerpt"),
            )
            db.add(es)

    db.commit()
    advance_job(uid, db, status=JobStatus.VERIFYING, progress_percent=80,
                current_stage="Claim verification complete")

    # ── Stage 4: Audio Authenticity Detection ─────────────────────────────────
    advance_job(uid, db, status=JobStatus.DETECTING_AUDIO, progress_percent=85,
                current_stage="Analysing audio for synthetic/AI generation…")

    from ml.audio_detection.detector import detect_audio_authenticity
    from app.models.models import AudioAuthenticityResult

    auth = detect_audio_authenticity(audio_path)

    auth_record = AudioAuthenticityResult(
        job_id=uid,
        human_probability=auth["human_probability"],
        ai_probability=auth["ai_probability"],
        detection_confidence=auth["detection_confidence"],
        model_used=auth["model_used"],
        acoustic_features_json=auth.get("acoustic_features"),
    )
    db.add(auth_record)
    db.commit()

    advance_job(uid, db, status=JobStatus.DETECTING_AUDIO, progress_percent=95,
                current_stage="Audio authenticity analysis complete")

    # ── Stage 5: Synthesise verdicts & mark COMPLETED ─────────────────────────
    complete_job(uid, db)
