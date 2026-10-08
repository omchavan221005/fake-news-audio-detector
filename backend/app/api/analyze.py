"""
Analysis API router.

Endpoints:
  GET /api/analyze/{job_id}/status      — poll job progress
  GET /api/analyze/{job_id}/transcript  — fetch transcription + segments
  GET /api/analyze/{job_id}/claims      — fetch claims + verifications + evidence
  GET /api/analyze/{job_id}/results     — fetch full synthesized result dashboard data
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.models import (
    AnalysisJob,
    Claim,
    ClaimVerification,
    JobStatus,
)
from app.schemas.schemas import (
    AudioFileResponse,
    AudioAuthenticityOut,
    ClaimOut,
    ClaimsResponse,
    ContentVerificationSummary,
    FinalResultsResponse,
    JobStatusResponse,
    TranscriptSegment,
    TranscriptionResponse,
)
from app.services.job_service import get_job_or_404, get_full_job_or_404

logger = logging.getLogger("fnad.api.analyze")

router = APIRouter()


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Start analysis job for an uploaded audio file",
)
def start_analysis_job(
    payload: dict,
    db: Session = Depends(get_db),
):
    audio_file_id = payload.get("audio_file_id")
    if not audio_file_id:
        raise HTTPException(status_code=400, detail="audio_file_id is required")

    from app.services.audio_service import get_audio_file_or_404
    from app.services.job_service import create_job
    from app.workers.tasks import run_analysis_pipeline
    from app.workers.celery_app import submit_task

    audio_file = get_audio_file_or_404(audio_file_id, db)
    job = create_job(audio_file, db)
    submit_task(run_analysis_pipeline, str(job.id))

    return {
        "id": str(job.id),
        "job_id": str(job.id),
        "audio_file_id": str(audio_file.id),
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "progress_percent": job.progress_percent,
        "current_stage": job.current_stage,
        "message": "Analysis job queued.",
    }


@router.get(
    "/{job_id}",
    summary="Fetch full synthesized result dashboard data",
)
def get_job_full(job_id: str, db: Session = Depends(get_db)):
    job = get_full_job_or_404(job_id, db)
    af = job.audio_file

    t = job.transcription
    transcription_data = {
        "full_text": t.full_text if t else "",
        "detected_language": t.detected_language if t else None,
        "detected_language_prob": t.detected_language_prob if t else None,
        "segments_json": t.segments_json if t else [],
    } if t else None

    claims_data = []
    for c in job.claims:
        c_dict = {
            "id": str(c.id),
            "claim_text": c.claim_text,
            "order_index": c.order_index,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "verification": {
                "classification": c.verification.classification.value if c.verification else "UNVERIFIED",
                "confidence": c.verification.confidence if c.verification else 0.5,
                "explanation": c.verification.explanation if c.verification else "",
                "sources": [
                    {
                        "title": s.source_title,
                        "url": s.source_url,
                        "domain": s.source_domain,
                        "source_type": s.source_type.value if hasattr(s.source_type, "value") else str(s.source_type),
                        "credibility_score": s.domain_credibility_score,
                        "stance": s.stance.value if hasattr(s.stance, "value") else str(s.stance),
                        "excerpt": s.excerpt,
                    }
                    for s in c.verification.evidence_sources
                ] if c.verification else [],
            } if c.verification else None,
        }
        claims_data.append(c_dict)

    auth = job.audio_authenticity_result
    auth_data = {
        "human_probability": auth.human_probability if auth else 0.5,
        "ai_probability": auth.ai_probability if auth else 0.5,
        "detection_confidence": auth.detection_confidence if auth else 0.0,
        "model_used": auth.model_used if auth else "Acoustic-Forensics-v1",
        "acoustic_features": auth.acoustic_features_json if auth else {},
    } if auth else None

    return {
        "id": str(job.id),
        "job_id": str(job.id),
        "status": job.status.value if hasattr(job.status, "value") else str(job.status),
        "progress_percent": job.progress_percent,
        "current_stage": job.current_stage,
        "error_message": job.error_message,
        "overall_credibility": job.overall_credibility.value if job.overall_credibility else None,
        "overall_authenticity": job.overall_authenticity.value if job.overall_authenticity else None,
        "overall_risk_level": job.overall_risk_level.value if job.overall_risk_level else None,
        "overall_risk_score": job.overall_risk_score,
        "synthesis_explanation": job.synthesis_explanation,
        "audio_file": {
            "id": str(af.id) if af else None,
            "original_filename": af.original_filename if af else None,
            "mime_type": af.mime_type if af else None,
            "file_size_bytes": af.file_size_bytes if af else None,
            "duration_seconds": af.duration_seconds if af else None,
            "sample_rate": af.sample_rate if af else None,
        } if af else None,
        "transcription": transcription_data,
        "claims": claims_data,
        "audio_authenticity_result": auth_data,
    }


@router.get(
    "/{job_id}/status",
    response_model=JobStatusResponse,
    summary="Poll analysis job progress",
)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = get_job_or_404(job_id, db)
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress_percent=job.progress_percent,
        current_stage=job.current_stage,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


@router.get(
    "/{job_id}/transcript",
    response_model=TranscriptionResponse,
    summary="Fetch speech-to-text transcript",
)
def get_transcript(job_id: str, db: Session = Depends(get_db)):
    job = get_job_or_404(job_id, db)
    if job.status == JobStatus.PENDING or job.status == JobStatus.TRANSCRIBING:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Transcript not ready yet. Job status: {job.status.value}",
        )

    t = job.transcription
    if t is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcription not found.")

    segments = []
    if t.segments_json:
        for seg in t.segments_json:
            segments.append(
                TranscriptSegment(
                    id=seg.get("id", 0),
                    start=seg.get("start", 0.0),
                    end=seg.get("end", 0.0),
                    text=seg.get("text", ""),
                    words=seg.get("words"),
                )
            )

    return TranscriptionResponse(
        job_id=job.id,
        detected_language=t.detected_language,
        detected_language_prob=t.detected_language_prob,
        full_text=t.full_text,
        segments=segments,
    )


@router.get(
    "/{job_id}/claims",
    response_model=ClaimsResponse,
    summary="Fetch extracted claims with verification results",
)
def get_claims(job_id: str, db: Session = Depends(get_db)):
    job = (
        db.query(AnalysisJob)
        .options(
            joinedload(AnalysisJob.claims).joinedload(Claim.verification).joinedload(
                ClaimVerification.evidence_sources
            )
        )
        .filter(AnalysisJob.id == uuid.UUID(job_id))
        .first()
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    if job.status not in (JobStatus.COMPLETED, JobStatus.VERIFYING, JobStatus.DETECTING_AUDIO):
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Claims not ready yet. Job status: {job.status.value}",
        )

    claims_out = [ClaimOut.model_validate(c) for c in job.claims]
    return ClaimsResponse(
        job_id=job.id,
        claims_count=len(claims_out),
        claims=claims_out,
    )


@router.get(
    "/{job_id}/results",
    response_model=FinalResultsResponse,
    summary="Fetch full synthesized analysis results",
)
def get_results(job_id: str, db: Session = Depends(get_db)):
    job = get_full_job_or_404(job_id, db)

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_425_TOO_EARLY,
            detail=f"Results not ready yet. Job status: {job.status.value}",
        )

    # ── Audio file info ──────────────────────────────────────────────────────────
    af = job.audio_file
    audio_file_resp = AudioFileResponse(
        audio_file_id=af.id,
        filename=af.original_filename,
        mime_type=af.mime_type,
        file_size_bytes=af.file_size_bytes,
        duration_seconds=af.duration_seconds,
        sample_rate=af.sample_rate,
        uploaded_at=af.uploaded_at,
    )

    # ── Content credibility summary ──────────────────────────────────────────────
    from app.models.models import ClaimClassification
    counts: dict[str, int] = {v.value.lower(): 0 for v in ClaimClassification}
    total_conf = 0.0
    n_verified = 0
    for claim in job.claims:
        if claim.verification:
            key = claim.verification.classification.value.lower()
            counts[key] = counts.get(key, 0) + 1
            total_conf += claim.verification.confidence
            n_verified += 1

    avg_conf = total_conf / n_verified if n_verified else 0.5

    content_summary = ContentVerificationSummary(
        verdict=job.overall_credibility,
        confidence=round(avg_conf, 4),
        claims_summary=counts,
    ) if job.overall_credibility else None

    # ── Audio authenticity ───────────────────────────────────────────────────────
    auth_result = job.audio_authenticity_result
    auth_out = None
    if auth_result:
        ai_p = auth_result.ai_probability
        if ai_p >= 0.7:
            verdict_label = "LIKELY_AI_GENERATED"
        elif ai_p >= 0.4:
            verdict_label = "POSSIBLY_AI_GENERATED"
        else:
            verdict_label = "LIKELY_HUMAN"

        auth_out = AudioAuthenticityOut(
            human_probability=auth_result.human_probability,
            ai_probability=auth_result.ai_probability,
            detection_confidence=auth_result.detection_confidence,
            model_used=auth_result.model_used,
            verdict=verdict_label,
            acoustic_features=auth_result.acoustic_features_json,
        )

    # ── Overall assessment ───────────────────────────────────────────────────────
    overall = {
        "risk_level": job.overall_risk_level.value if job.overall_risk_level else None,
        "risk_score": job.overall_risk_score,
        "explanation": job.synthesis_explanation,
        "disclaimer": (
            "These results are model-assisted assessments and should not be treated as "
            "absolute proof. AI-generated audio detection can produce false positives/negatives. "
            "Fact verification depends on the quality of available evidence. "
            "Results should be independently verified for high-stakes claims."
        ),
    }

    return FinalResultsResponse(
        job_id=job.id,
        status=job.status,
        audio_file=audio_file_resp,
        content_verification=content_summary,
        audio_authenticity=auth_out,
        overall_assessment=overall,
    )


@router.get(
    "/{job_id}/export",
    summary="Export forensic audit report in JSON, Markdown, or CSV format",
)
def export_report(
    job_id: str,
    format: str = "json",
    db: Session = Depends(get_db),
):
    from fastapi.responses import Response, JSONResponse
    import io
    import csv

    job = get_full_job_or_404(job_id, db)
    af = job.audio_file
    full_data = get_job_full(job_id, db)

    fmt = format.lower().strip()
    if fmt == "json":
        return JSONResponse(
            content=full_data,
            headers={
                "Content-Disposition": f'attachment; filename="fake_news_audit_report_{job_id[:8]}.json"',
            },
        )
    elif fmt == "markdown" or fmt == "md":
        md_lines = [
            f"# 🎙️ Fake News Audio Detection & Forensic Audit Report",
            f"**Job ID:** `{job_id}`  ",
            f"**File:** `{af.original_filename if af else 'unknown'}`  ",
            f"**Duration:** {af.duration_seconds if af else 'N/A'}s  ",
            f"**Created At:** {job.created_at}  ",
            f"",
            f"---",
            f"",
            f"## 📊 Executive Verdict",
            f"- **Content Credibility:** `{job.overall_credibility.value if job.overall_credibility else 'UNVERIFIED'}`",
            f"- **Audio Authenticity:** `{job.overall_authenticity.value if job.overall_authenticity else 'UNKNOWN'}`",
            f"- **Calibrated Risk Level:** `{job.overall_risk_level.value if job.overall_risk_level else 'UNKNOWN'}` (Score: {job.overall_risk_score:.2f})",
            f"",
            f"**Analysis Summary:** {job.synthesis_explanation or 'N/A'}",
            f"",
            f"---",
            f"",
            f"## 📝 Full Transcript",
            f"{job.transcription.full_text if job.transcription else 'No transcript generated.'}",
            f"",
            f"---",
            f"",
            f"## 🔍 Extracted Claims & Fact-Checking Evidence",
        ]
        if job.claims:
            for i, c in enumerate(job.claims, 1):
                ver = c.verification
                status_str = ver.classification.value if ver and ver.classification else "UNVERIFIED"
                conf_str = f"({ver.confidence * 100:.1f}% confidence)" if ver else ""
                md_lines.append(f"### Claim #{i} [{status_str}] {conf_str}")
                md_lines.append(f"> \"{c.claim_text}\" (Timestamp: {c.start_time:.1f}s - {c.end_time:.1f}s)")
                if ver and ver.explanation:
                    md_lines.append(f"\n**Verdict Explanation:** {ver.explanation}")
                if ver and ver.evidence_snippets:
                    md_lines.append("\n**Cited Sources:**")
                    for ev in ver.evidence_snippets:
                        md_lines.append(f"- **[{ev.domain}]({ev.url}):** {ev.snippet} *(Stance: {ev.stance.value if ev.stance else 'neutral'})*")
                md_lines.append("")
        else:
            md_lines.append("No factual claims were extracted from this audio.")

        md_content = "\n".join(md_lines)
        return Response(
            content=md_content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="fake_news_audit_report_{job_id[:8]}.md"',
            },
        )
    elif fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Claim #", "Claim Text", "Start Time (s)", "End Time (s)", "Verdict", "Confidence", "Evidence Count"])
        for i, c in enumerate(job.claims, 1):
            ver = c.verification
            writer.writerow([
                i,
                c.claim_text,
                c.start_time,
                c.end_time,
                ver.classification.value if ver and ver.classification else "UNVERIFIED",
                f"{ver.confidence:.2f}" if ver else "0.0",
                len(ver.evidence_snippets) if ver and ver.evidence_snippets else 0,
            ])
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="claims_report_{job_id[:8]}.csv"',
            },
        )
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported formats: json, markdown, csv")
