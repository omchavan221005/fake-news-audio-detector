"""
Pydantic v2 request / response schemas.

Separating schemas from ORM models means API contracts can evolve
independently of the database structure.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from app.models.models import (
    JobStatus,
    ClaimClassification,
    CredibilityVerdict,
    AuthenticityVerdict,
    RiskLevel,
    SourceType,
    Stance,
)


# ── Audio Upload ────────────────────────────────────────────────────────────────

class AudioFileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audio_file_id: uuid.UUID
    filename: str
    mime_type: str
    file_size_bytes: int | None
    duration_seconds: float | None
    sample_rate: int | None
    uploaded_at: datetime


# ── Job ─────────────────────────────────────────────────────────────────────────

class JobCreateResponse(BaseModel):
    job_id: uuid.UUID
    audio_file_id: uuid.UUID
    status: JobStatus
    message: str


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: JobStatus
    progress_percent: int
    current_stage: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


# ── Transcription ────────────────────────────────────────────────────────────────

class TranscriptSegment(BaseModel):
    id: int
    start: float
    end: float
    text: str
    words: list[dict[str, Any]] | None = None


class TranscriptionResponse(BaseModel):
    job_id: uuid.UUID
    detected_language: str | None
    detected_language_prob: float | None
    full_text: str
    segments: list[TranscriptSegment]


# ── Claims ───────────────────────────────────────────────────────────────────────

class EvidenceSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source_title: str | None
    source_url: str
    source_domain: str | None
    source_type: SourceType
    domain_credibility_score: float | None
    stance: Stance
    publication_date: datetime | None
    excerpt: str | None


class ClaimVerificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    classification: ClaimClassification
    confidence: float
    explanation: str
    evidence_sources: list[EvidenceSourceOut] = []


class ClaimOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    order: int = Field(alias="order_index")
    claim_text: str
    start_time: float | None
    end_time: float | None
    verification: ClaimVerificationOut | None = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ClaimsResponse(BaseModel):
    job_id: uuid.UUID
    claims_count: int
    claims: list[ClaimOut]


# ── Audio Authenticity ───────────────────────────────────────────────────────────

class AudioAuthenticityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    human_probability: float
    ai_probability: float
    detection_confidence: float
    model_used: str
    verdict: str   # derived label, set by service layer
    acoustic_features: dict[str, Any] | None = None


# ── Final Results ────────────────────────────────────────────────────────────────

class ContentVerificationSummary(BaseModel):
    verdict: CredibilityVerdict
    confidence: float
    claims_summary: dict[str, int]   # {"true": N, "false": N, ...}


class FinalResultsResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    audio_file: AudioFileResponse
    content_verification: ContentVerificationSummary | None
    audio_authenticity: AudioAuthenticityOut | None
    overall_assessment: dict[str, Any] | None   # risk_level, explanation, risk_score
