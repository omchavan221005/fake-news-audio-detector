"""
Job service — manages the AnalysisJob lifecycle.

Responsible for creating jobs, updating their stage/progress,
and querying results. The actual ML pipeline execution is handled
by the background worker (app/workers/celery_app.py).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    AnalysisJob,
    AudioFile,
    JobStatus,
    Transcription,
    Claim,
    ClaimVerification,
    EvidenceSource,
    AudioAuthenticityResult,
    CredibilityVerdict,
    AuthenticityVerdict,
    RiskLevel,
    ClaimClassification,
)

logger = logging.getLogger("fnad.job_service")


def create_job(audio_file: AudioFile, db: Session) -> AnalysisJob:
    """Create and persist a new PENDING analysis job for an audio file."""
    job = AnalysisJob(
        audio_file_id=audio_file.id,
        status=JobStatus.PENDING,
        progress_percent=0,
        current_stage="Queued — waiting to start",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created AnalysisJob %s for AudioFile %s", job.id, audio_file.id)
    return job


def get_job_or_404(job_id: str, db: Session) -> AnalysisJob:
    """Fetch an AnalysisJob by UUID string, raise 404 if missing."""
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    job = db.query(AnalysisJob).filter(AnalysisJob.id == uid).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def get_full_job_or_404(job_id: str, db: Session) -> AnalysisJob:
    """
    Fetch job with all relationships eagerly loaded (for /results endpoint).
    """
    try:
        uid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    job = (
        db.query(AnalysisJob)
        .options(
            joinedload(AnalysisJob.audio_file),
            joinedload(AnalysisJob.transcription),
            joinedload(AnalysisJob.claims).joinedload(Claim.verification).joinedload(
                ClaimVerification.evidence_sources
            ),
            joinedload(AnalysisJob.audio_authenticity_result),
        )
        .filter(AnalysisJob.id == uid)
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")
    return job


def advance_job(
    job_id: uuid.UUID,
    db: Session,
    *,
    status: JobStatus,
    progress_percent: int,
    current_stage: str,
) -> None:
    """Update job status, progress, and stage label in-place."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        logger.warning("advance_job: job %s not found", job_id)
        return

    job.status = status
    job.progress_percent = progress_percent
    job.current_stage = current_stage
    db.commit()


def fail_job(job_id: uuid.UUID, db: Session, error_message: str) -> None:
    """Mark a job as FAILED with an error message."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        return
    job.status = JobStatus.FAILED
    job.error_message = error_message
    job.current_stage = "Analysis failed"
    db.commit()
    logger.error("Job %s failed: %s", job_id, error_message)


def complete_job(job_id: uuid.UUID, db: Session) -> None:
    """
    Mark a job as COMPLETED, derive the synthesized dual verdict,
    and set overall_risk_level + synthesis_explanation.
    """
    job = (
        db.query(AnalysisJob)
        .options(
            joinedload(AnalysisJob.claims).joinedload(Claim.verification),
            joinedload(AnalysisJob.audio_authenticity_result),
        )
        .filter(AnalysisJob.id == job_id)
        .first()
    )
    if not job:
        return

    # ── Derive content credibility verdict ──────────────────────────────────────
    verifications = [
        c.verification for c in job.claims if c.verification is not None
    ]
    counts = {cls: 0 for cls in ClaimClassification}
    for v in verifications:
        counts[v.classification] = counts.get(v.classification, 0) + 1

    total = len(verifications)
    if total == 0:
        credibility = CredibilityVerdict.UNVERIFIED
        credibility_conf = 0.5
    else:
        false_ratio = counts.get(ClaimClassification.FALSE, 0) / total
        misleading_ratio = counts.get(ClaimClassification.MISLEADING, 0) / total
        true_ratio = counts.get(ClaimClassification.TRUE, 0) / total
        unverified_ratio = counts.get(ClaimClassification.UNVERIFIED, 0) / total

        if false_ratio >= 0.5:
            credibility = CredibilityVerdict.LIKELY_FALSE
            credibility_conf = 0.6 + false_ratio * 0.35
        elif misleading_ratio >= 0.4 or (false_ratio + misleading_ratio) >= 0.5:
            credibility = CredibilityVerdict.MISLEADING
            credibility_conf = 0.55 + misleading_ratio * 0.4
        elif true_ratio >= 0.5:
            credibility = CredibilityVerdict.LIKELY_TRUE
            credibility_conf = 0.6 + true_ratio * 0.35
        else:
            credibility = CredibilityVerdict.UNVERIFIED
            credibility_conf = 0.5

    # ── Derive audio authenticity verdict ───────────────────────────────────────
    auth_result = job.audio_authenticity_result
    if auth_result is None:
        authenticity = AuthenticityVerdict.INCONCLUSIVE
        ai_prob = 0.5
    else:
        ai_prob = auth_result.ai_probability
        if ai_prob >= 0.7:
            authenticity = AuthenticityVerdict.LIKELY_AI
        elif ai_prob >= 0.4:
            authenticity = AuthenticityVerdict.POSSIBLY_MANIPULATED
        else:
            authenticity = AuthenticityVerdict.LIKELY_HUMAN

    # ── Risk matrix ─────────────────────────────────────────────────────────────
    # credibility_risk: LIKELY_FALSE=1.0, MISLEADING=0.7, UNVERIFIED=0.4, LIKELY_TRUE=0.1
    cred_risk_map = {
        CredibilityVerdict.LIKELY_FALSE: 1.0,
        CredibilityVerdict.MISLEADING: 0.7,
        CredibilityVerdict.UNVERIFIED: 0.4,
        CredibilityVerdict.LIKELY_TRUE: 0.1,
    }
    cred_risk = cred_risk_map.get(credibility, 0.4)
    auth_risk = ai_prob  # 0.0–1.0 directly maps to risk contribution

    # Weighted combination: content credibility is the dominant signal
    risk_score = round(0.65 * cred_risk + 0.35 * auth_risk, 4)

    if risk_score >= 0.75:
        risk_level = RiskLevel.CRITICAL
    elif risk_score >= 0.5:
        risk_level = RiskLevel.HIGH
    elif risk_score >= 0.25:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    explanation = (
        f"Content credibility: {credibility.value} (confidence {credibility_conf:.0%}). "
        f"Audio authenticity: {authenticity.value} (AI probability {ai_prob:.0%}). "
        "Note: these are independent signals — AI-generated audio does not imply false content, "
        "and human audio does not imply true content."
    )

    job.status = JobStatus.COMPLETED
    job.progress_percent = 100
    job.current_stage = "Analysis complete"
    job.overall_credibility = credibility
    job.overall_authenticity = authenticity
    job.overall_risk_level = risk_level
    job.overall_risk_score = risk_score
    job.synthesis_explanation = explanation
    job.completed_at = datetime.utcnow()
    db.commit()

    logger.info(
        "Job %s COMPLETED — credibility=%s authenticity=%s risk=%s (%.2f)",
        job_id, credibility.value, authenticity.value, risk_level.value, risk_score,
    )
