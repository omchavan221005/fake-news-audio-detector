"""
ORM models — mirrors the Phase 1 architecture schema.

Kept deliberately plain (no business logic here).
Services/ owns behaviour; models/ owns structure and relationships.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Column,
    String,
    Float,
    Integer,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    JSON,
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type: uses PG UUID on Postgres, CHAR(36) on SQLite."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


def UUID(as_uuid=True):
    return GUID()


def gen_uuid():
    return uuid.uuid4()


# ── Enumerations ───────────────────────────────────────────────────────────────

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    TRANSCRIBING = "TRANSCRIBING"
    EXTRACTING_CLAIMS = "EXTRACTING_CLAIMS"
    VERIFYING = "VERIFYING"
    DETECTING_AUDIO = "DETECTING_AUDIO"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CredibilityVerdict(str, enum.Enum):
    LIKELY_TRUE = "LIKELY_TRUE"
    LIKELY_FALSE = "LIKELY_FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"


class AuthenticityVerdict(str, enum.Enum):
    LIKELY_HUMAN = "LIKELY_HUMAN"
    LIKELY_AI = "LIKELY_AI"
    POSSIBLY_MANIPULATED = "POSSIBLY_MANIPULATED"
    INCONCLUSIVE = "INCONCLUSIVE"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ClaimClassification(str, enum.Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"


class SourceType(str, enum.Enum):
    GOVERNMENT = "government"
    NEWS = "news"
    ACADEMIC = "academic"
    PRIMARY = "primary"
    OTHER = "other"


class Stance(str, enum.Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


# ── Tables ─────────────────────────────────────────────────────────────────────

class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    mime_type = Column(String(64), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("AnalysisJob", back_populates="audio_file")


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    audio_file_id = Column(UUID(as_uuid=True), ForeignKey("audio_files.id"), nullable=False)

    # Pipeline state
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    current_stage = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)

    # Synthesised verdicts (set on COMPLETED)
    overall_credibility = Column(Enum(CredibilityVerdict), nullable=True)
    overall_authenticity = Column(Enum(AuthenticityVerdict), nullable=True)
    overall_risk_level = Column(Enum(RiskLevel), nullable=True)
    overall_risk_score = Column(Float, nullable=True)   # 0.0 – 1.0
    synthesis_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    audio_file = relationship("AudioFile", back_populates="jobs")
    transcription = relationship("Transcription", back_populates="job", uselist=False)
    claims = relationship("Claim", back_populates="job", order_by="Claim.order_index")
    audio_authenticity_result = relationship(
        "AudioAuthenticityResult", back_populates="job", uselist=False
    )


class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), nullable=False)
    full_text = Column(Text, nullable=False)
    detected_language = Column(String(16), nullable=True)
    detected_language_prob = Column(Float, nullable=True)
    # List of {id, start, end, text, words?: [{word, start, end, prob}]}
    segments_json = Column(JSON, nullable=True)

    job = relationship("AnalysisJob", back_populates="transcription")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), nullable=False)
    claim_text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False)
    start_time = Column(Float, nullable=True)   # seconds into audio
    end_time = Column(Float, nullable=True)

    job = relationship("AnalysisJob", back_populates="claims")
    verification = relationship("ClaimVerification", back_populates="claim", uselist=False)


class ClaimVerification(Base):
    __tablename__ = "claim_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    classification = Column(Enum(ClaimClassification), nullable=False)
    confidence = Column(Float, nullable=False)
    explanation = Column(Text, nullable=False)

    claim = relationship("Claim", back_populates="verification")
    evidence_sources = relationship("EvidenceSource", back_populates="claim_verification")


class EvidenceSource(Base):
    __tablename__ = "evidence_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    claim_verification_id = Column(
        UUID(as_uuid=True), ForeignKey("claim_verifications.id"), nullable=False
    )
    source_title = Column(String(255), nullable=True)
    source_url = Column(Text, nullable=False)
    source_domain = Column(String(128), nullable=True)
    source_type = Column(Enum(SourceType), nullable=False)
    domain_credibility_score = Column(Float, nullable=True)  # 0.0 – 1.0
    stance = Column(Enum(Stance), nullable=False)
    publication_date = Column(DateTime, nullable=True)
    excerpt = Column(Text, nullable=True)

    claim_verification = relationship("ClaimVerification", back_populates="evidence_sources")


class AudioAuthenticityResult(Base):
    __tablename__ = "audio_authenticity_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id = Column(UUID(as_uuid=True), ForeignKey("analysis_jobs.id"), nullable=False)
    human_probability = Column(Float, nullable=False)
    ai_probability = Column(Float, nullable=False)
    detection_confidence = Column(Float, nullable=False)
    model_used = Column(String(128), nullable=False)
    # Dict of acoustic features: jitter, shimmer, spectral_flatness, zcr, etc.
    acoustic_features_json = Column(JSON, nullable=True)

    job = relationship("AnalysisJob", back_populates="audio_authenticity_result")
