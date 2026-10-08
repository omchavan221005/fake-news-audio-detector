"""
Phase 5 Tests — Claim Extraction & Check-Worthiness Analysis

Tests:
  1. Sentence boundary splitting with abbreviations and decimals.
  2. Noise, greeting, opinion, and question filtering.
  3. Positive check-worthiness detection (numbers, dates, entities, reporting verbs).
  4. Audio segment timestamp alignment.
  5. Claim deduplication.
  6. End-to-end extraction from realistic mixed news and podcast transcripts.
  7. Edge cases (empty transcript, single sentence, pure chatter).
"""
from __future__ import annotations

import os
import sys
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from ml.claim_extraction.extractor import (
    split_into_sentences,
    compute_check_worthiness,
    align_timestamps,
    deduplicate_claims,
    extract_claims,
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Sentence Boundary Detection
# ─────────────────────────────────────────────────────────────────────────────

def test_sentence_splitter_basic():
    text = "The president signed the treaty. It took effect immediately! Will it last?"
    sentences = split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0] == "The president signed the treaty."
    assert sentences[1] == "It took effect immediately!"
    assert sentences[2] == "Will it last?"


def test_sentence_splitter_abbreviations_and_decimals():
    text = (
        "In the U.S. today, Dr. Smith reported a 15.5% increase in funding. "
        "The project costs $2.5 million."
    )
    sentences = split_into_sentences(text)
    assert len(sentences) == 2
    assert "U.S." in sentences[0]
    assert "Dr." in sentences[0]
    assert "15.5%" in sentences[0]
    assert "$2.5 million" in sentences[1]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Check-Worthiness Filter (Noise Rejection)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "noise_phrase",
    [
        "Hello everyone, welcome back to our podcast!",
        "Hi guys, good morning and welcome!",
        "Don't forget to like and subscribe to the channel.",
        "Hit the bell icon and leave a comment below.",
        "Thanks for watching, see you tomorrow!",
        "What do you guys think about this?",
        "Why did this happen so suddenly?",
        "Um, yeah, okay.",
        "To be honest, I personally feel this was not great.",
    ],
)
def test_filter_rejects_noise_and_chatter(noise_phrase):
    is_claim, score, reasons = compute_check_worthiness(noise_phrase)
    assert not is_claim, f"Expected '{noise_phrase}' to be rejected, but got score {score} ({reasons})"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Check-Worthiness Filter (Positive Claims)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "factual_claim",
    [
        "The World Health Organization announced that global infections dropped by 35% in 2024.",
        "Congress passed a 500 million dollar infrastructure bill on March 12.",
        "Researchers at Oxford University published a study finding that the vaccine prevented 80% of hospitalizations.",
        "The Prime Minister resigned following the investigation by the federal police.",
        "NASA successfully launched the Europa Clipper spacecraft on a five-year mission.",
    ],
)
def test_detects_verifiable_factual_claims(factual_claim):
    is_claim, score, reasons = compute_check_worthiness(factual_claim)
    assert is_claim, f"Expected '{factual_claim}' to be classified as claim, but got score {score} ({reasons})"
    assert score >= 0.40


# ─────────────────────────────────────────────────────────────────────────────
# 4. Timestamp Alignment
# ─────────────────────────────────────────────────────────────────────────────

def test_align_timestamps_matching_segment():
    segments = [
        {"id": 0, "start": 0.0, "end": 3.0, "text": "Welcome back to the show."},
        {
            "id": 1,
            "start": 3.1,
            "end": 8.5,
            "text": "The government increased fuel taxes by 20 percent yesterday.",
        },
        {"id": 2, "start": 8.6, "end": 12.0, "text": "Thanks for listening."},
    ]
    sentence = "The government increased fuel taxes by 20 percent yesterday."
    start_t, end_t = align_timestamps(sentence, segments)

    assert start_t == pytest.approx(3.1, 0.1)
    assert end_t == pytest.approx(8.5, 0.1)


def test_align_timestamps_empty_segments():
    start_t, end_t = align_timestamps("A factual sentence.", [])
    assert start_t is None
    assert end_t is None


# ─────────────────────────────────────────────────────────────────────────────
# 5. Deduplication
# ─────────────────────────────────────────────────────────────────────────────

def test_deduplicate_claims():
    claims = [
        {"text": "The government raised fuel taxes by 20 percent.", "confidence": 0.7, "start_time": 1.0, "end_time": 4.0},
        {"text": "The government raised the fuel taxes by 20 percent.", "confidence": 0.85, "start_time": 12.0, "end_time": 15.0},
        {"text": "In other news, NASA discovered a new exoplanet.", "confidence": 0.8, "start_time": 20.0, "end_time": 25.0},
    ]
    deduped = deduplicate_claims(claims, threshold=0.70)
    assert len(deduped) == 2
    # Check that highest score was preserved
    assert deduped[0]["confidence"] == 0.85


# ─────────────────────────────────────────────────────────────────────────────
# 6. End-to-End Claim Extraction
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_claims_realistic_mixed_transcript():
    transcript = (
        "Good morning everyone, welcome back to Daily News Digest! "
        "Don't forget to hit like and subscribe. "
        "The World Health Organization confirmed 1200 new cases in March 2024. "
        "I personally think this is very concerning. "
        "Did you know that the EU banned single-use plastics last week? "
        "The treasury allocated 2 billion euros to renewable energy programs. "
        "Thank you all for tuning in today, see you next time!"
    )
    segments = [
        {"id": 0, "start": 0.0, "end": 4.0, "text": "Good morning everyone, welcome back to Daily News Digest!"},
        {"id": 1, "start": 4.1, "end": 7.0, "text": "Don't forget to hit like and subscribe."},
        {"id": 2, "start": 7.1, "end": 13.0, "text": "The World Health Organization confirmed 1200 new cases in March 2024."},
        {"id": 3, "start": 13.1, "end": 16.0, "text": "I personally think this is very concerning."},
        {"id": 4, "start": 16.1, "end": 20.0, "text": "Did you know that the EU banned single-use plastics last week?"},
        {"id": 5, "start": 20.1, "end": 26.0, "text": "The treasury allocated 2 billion euros to renewable energy programs."},
        {"id": 6, "start": 26.1, "end": 30.0, "text": "Thank you all for tuning in today, see you next time!"},
    ]

    claims = extract_claims(transcript, segments)

    # Should retain the WHO claim and the treasury claim, discarding the greetings, CTAs, and chatter
    assert len(claims) >= 2

    claim_texts = [c["text"] for c in claims]
    assert any("World Health Organization" in ct for ct in claim_texts)
    assert any("2 billion euros" in ct for ct in claim_texts)

    # Ensure greetings and subscriptions are not present in claims
    assert not any("welcome back" in ct.lower() for ct in claim_texts)
    assert not any("subscribe" in ct.lower() for ct in claim_texts)
    assert not any("see you next time" in ct.lower() for ct in claim_texts)

    # Check timestamps and fields
    for cl in claims:
        assert "text" in cl
        assert "start_time" in cl
        assert "end_time" in cl
        assert "confidence" in cl
        assert cl["start_time"] is not None


def test_extract_claims_empty_text():
    claims = extract_claims("", [])
    assert claims == []


def test_extract_claims_max_claims_cap():
    # Long text with 5 factual claims
    claims_text = ". ".join([
        f"Study {i} confirmed that {i*10} percent of subjects improved in {2020+i}"
        for i in range(5)
    ]) + "."

    claims = extract_claims(claims_text, max_claims=2)
    assert len(claims) <= 2
