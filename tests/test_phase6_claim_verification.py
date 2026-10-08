"""
Phase 6 Tests — Claim Verification & Fact-Checking (Evidence Retrieval + NLI)

Tests:
  1. Domain credibility classification & reputation scoring.
  2. Search query extraction.
  3. Evidence retrieval with mocked network responses & timeout resilience.
  4. NLI stance detection (supports, contradicts, neutral).
  5. Verdict synthesis (TRUE, FALSE, CONFLICTING, UNVERIFIED).
  6. End-to-end verification pipeline compatibility with DB models.
"""
from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch
import pytest

# Ensure backend directory is in sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.models.models import ClaimClassification, SourceType, Stance
from ml.claim_verification.domain_credibility import classify_domain, extract_domain
from ml.claim_verification.evidence_retriever import generate_search_query, retrieve_evidence
from ml.claim_verification.nli_engine import determine_stance
from ml.claim_verification.verifier import verify_claims, _synthesize_verdict


# ─────────────────────────────────────────────────────────────────────────────
# 1. Domain Credibility Profiler
# ─────────────────────────────────────────────────────────────────────────────

def test_extract_domain():
    assert extract_domain("https://www.reuters.com/article/123") == "reuters.com"
    assert extract_domain("http://who.int/news/item") == "who.int"
    assert extract_domain("subdomain.cdc.gov/data") == "subdomain.cdc.gov"


@pytest.mark.parametrize(
    "url,expected_type,min_score",
    [
        ("https://www.who.int/emergencies", SourceType.GOVERNMENT, 0.95),
        ("https://data.cdc.gov/health", SourceType.GOVERNMENT, 0.95),
        ("https://www.nature.com/articles/s41586", SourceType.ACADEMIC, 0.95),
        ("https://news.harvard.edu/gazette", SourceType.ACADEMIC, 0.90),
        ("https://www.snopes.com/fact-check/test", SourceType.PRIMARY, 0.90),
        ("https://en.wikipedia.org/wiki/Earth", SourceType.PRIMARY, 0.85),
        ("https://www.reuters.com/business", SourceType.NEWS, 0.90),
        ("https://www.bbc.com/news", SourceType.NEWS, 0.90),
        ("https://apnews.com/article/press", SourceType.NEWS, 0.90),
    ],
)
def test_domain_classification_high_credibility(url, expected_type, min_score):
    stype, score, domain = classify_domain(url)
    assert stype == expected_type
    assert score >= min_score


def test_domain_classification_satire_low_credibility():
    stype, score, domain = classify_domain("https://theonion.com/some-fake-story")
    assert score <= 0.20


def test_domain_classification_unknown():
    stype, score, domain = classify_domain("https://random-personal-blog-123.org")
    assert stype == SourceType.OTHER
    assert 0.50 <= score <= 0.60


# ─────────────────────────────────────────────────────────────────────────────
# 2. Query Generation
# ─────────────────────────────────────────────────────────────────────────────

def test_generate_search_query():
    claim = "According to reports, the World Health Organization confirmed 1200 new cases in March 2024!"
    query = generate_search_query(claim)
    assert "World Health Organization" in query
    assert "1200" in query
    assert "According to reports" not in query
    assert len(query.split()) <= 12


# ─────────────────────────────────────────────────────────────────────────────
# 3. Evidence Retrieval Mocking & Resilience
# ─────────────────────────────────────────────────────────────────────────────

def test_retrieve_evidence_wikipedia_mock():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "query": {
            "search": [
                {
                    "title": "World Health Organization",
                    "snippet": "The <span class=\"searchmatch\">WHO</span> confirmed global decline in cases.",
                    "pageid": 12345,
                }
            ]
        }
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        evidence = retrieve_evidence("WHO announced global decline", max_results=1)

    assert len(evidence) == 1
    ev = evidence[0]
    assert "Wikipedia: World Health Organization" in ev["title"]
    assert "WHO confirmed global decline" in ev["snippet"]
    assert ev["domain"] == "en.wikipedia.org"
    assert ev["source_type"] == SourceType.PRIMARY
    assert ev["credibility_score"] >= 0.85


def test_retrieve_evidence_timeout_resilience():
    """Verify that network exceptions or timeouts return empty list without crashing."""
    with patch("httpx.Client.get", side_effect=Exception("Connection timed out")):
        evidence = retrieve_evidence("Any search query")
    assert evidence == []


# ─────────────────────────────────────────────────────────────────────────────
# 4. NLI Stance Analysis
# ─────────────────────────────────────────────────────────────────────────────

def test_nli_stance_supports():
    claim = "The World Health Organization confirmed global infections dropped by 35% in 2024."
    evidence = "In March 2024, the World Health Organization confirmed that global infections dropped by 35% worldwide."
    stance, conf = determine_stance(claim, evidence)
    assert stance == Stance.SUPPORTS
    assert conf >= 0.70


def test_nli_stance_contradicts():
    claim = "The World Health Organization confirmed global infections dropped by 35% in 2024."
    evidence = "Independent fact-checkers debunked reports of a drop; official WHO data shows the claim is false and fabricated."
    stance, conf = determine_stance(claim, evidence)
    assert stance == Stance.CONTRADICTS
    assert conf >= 0.70


def test_nli_stance_neutral():
    claim = "NASA launched the Europa Clipper spacecraft on a five-year mission."
    evidence = "The solar system contains eight major planets and numerous dwarf planets and asteroids."
    stance, conf = determine_stance(claim, evidence)
    assert stance == Stance.NEUTRAL


# ─────────────────────────────────────────────────────────────────────────────
# 5. Verdict Synthesis
# ─────────────────────────────────────────────────────────────────────────────

def test_synthesis_true_verdict():
    sources = [
        {
            "domain": "reuters.com",
            "credibility_score": 0.95,
            "stance": Stance.SUPPORTS.value,
            "stance_confidence": 0.90,
        },
        {
            "domain": "who.int",
            "credibility_score": 0.98,
            "stance": Stance.SUPPORTS.value,
            "stance_confidence": 0.92,
        },
    ]
    verdict, conf, explanation = _synthesize_verdict("Sample claim", sources)
    assert verdict == ClaimClassification.TRUE
    assert conf >= 0.75
    assert "support" in explanation.lower()


def test_synthesis_false_verdict():
    sources = [
        {
            "domain": "snopes.com",
            "credibility_score": 0.95,
            "stance": Stance.CONTRADICTS.value,
            "stance_confidence": 0.92,
        },
        {
            "domain": "apnews.com",
            "credibility_score": 0.94,
            "stance": Stance.CONTRADICTS.value,
            "stance_confidence": 0.88,
        },
    ]
    verdict, conf, explanation = _synthesize_verdict("Sample false claim", sources)
    assert verdict == ClaimClassification.FALSE
    assert conf >= 0.75
    assert "contradicts" in explanation.lower()


def test_synthesis_conflicting_verdict():
    sources = [
        {
            "domain": "news1.com",
            "credibility_score": 0.85,
            "stance": Stance.SUPPORTS.value,
            "stance_confidence": 0.80,
        },
        {
            "domain": "news2.com",
            "credibility_score": 0.85,
            "stance": Stance.CONTRADICTS.value,
            "stance_confidence": 0.80,
        },
    ]
    verdict, conf, explanation = _synthesize_verdict("Controversial claim", sources)
    assert verdict == ClaimClassification.CONFLICTING


def test_synthesis_no_sources_unverified():
    verdict, conf, explanation = _synthesize_verdict("Unknown claim", [])
    assert verdict == ClaimClassification.UNVERIFIED
    assert conf == 0.50


# ─────────────────────────────────────────────────────────────────────────────
# 6. End-to-End verify_claims Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def test_verify_claims_mocked_e2e():
    mock_evidence = [
        {
            "title": "Reuters Fact Check",
            "url": "https://reuters.com/factcheck/item",
            "snippet": "Official health reports confirmed infections decreased 35% in 2024.",
            "domain": "reuters.com",
            "source_type": SourceType.NEWS,
            "credibility_score": 0.95,
        }
    ]

    with patch("ml.claim_verification.verifier.retrieve_evidence", return_value=mock_evidence):
        results = verify_claims(["Infections decreased 35% in 2024."])

    assert len(results) == 1
    res = results[0]
    assert res["classification"] == ClaimClassification.TRUE
    assert res["confidence"] >= 0.70
    assert len(res["sources"]) == 1
    assert res["sources"][0]["stance"] == Stance.SUPPORTS.value
    assert res["sources"][0]["source_type"] == "news"


def test_verify_claims_empty_list():
    assert verify_claims([]) == []
