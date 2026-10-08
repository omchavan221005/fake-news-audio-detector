"""
Claim Verification Orchestrator.

Wires together Evidence Retrieval, Domain Credibility Profiling, and NLI Stance
Analysis to synthesize a factual verdict (TRUE, FALSE, MISLEADING, CONFLICTING, UNVERIFIED)
for each extracted claim with explanatory rationale and citations.
"""
from __future__ import annotations

import logging
from typing import Any

from app.models.models import ClaimClassification, Stance
from ml.claim_verification.evidence_retriever import retrieve_evidence
from ml.claim_verification.nli_engine import determine_stance

logger = logging.getLogger("fnad.ml.claim_verification")


def _synthesize_verdict(claim: str, sources: list[dict[str, Any]]) -> tuple[ClaimClassification, float, str]:
    """
    Synthesize aggregated classification, confidence score, and explanation
    from weighted evidence sources.
    """
    if not sources:
        return (
            ClaimClassification.UNVERIFIED,
            0.50,
            "No verifiable evidence was found in available external sources to corroborate or refute this claim.",
        )

    supports = [s for s in sources if s["stance"] == Stance.SUPPORTS.value]
    contradicts = [s for s in sources if s["stance"] == Stance.CONTRADICTS.value]
    neutrals = [s for s in sources if s["stance"] == Stance.NEUTRAL.value]

    support_score = sum(s["credibility_score"] * s["stance_confidence"] for s in supports)
    contradict_score = sum(s["credibility_score"] * s["stance_confidence"] for s in contradicts)

    # 1. Predominantly Contradicted -> FALSE
    if contradict_score > 0 and (contradict_score >= support_score * 1.4 or not supports):
        top_src = sorted(contradicts, key=lambda x: x["credibility_score"], reverse=True)[0]
        confidence = min(0.95, round(0.65 + min(contradict_score, 1.0) * 0.25, 2))
        explanation = (
            f"External evidence contradicts this statement. Sources including {top_src.get('domain', 'trusted outlets')} "
            f"refute or debunk the claim."
        )
        return ClaimClassification.FALSE, confidence, explanation

    # 2. Predominantly Supported -> TRUE
    if support_score > 0 and (support_score >= contradict_score * 1.4 or not contradicts):
        top_src = sorted(supports, key=lambda x: x["credibility_score"], reverse=True)[0]
        confidence = min(0.95, round(0.65 + min(support_score, 1.0) * 0.25, 2))
        explanation = (
            f"Corroborating reporting and documentation support this claim. Verified by credible sources "
            f"including {top_src.get('domain', 'official records')}."
        )
        return ClaimClassification.TRUE, confidence, explanation

    # 3. Conflicting / Mixed Evidence -> MISLEADING or CONFLICTING
    if supports and contradicts:
        confidence = 0.68
        explanation = (
            f"Available evidence is mixed or conflicting. Found {len(supports)} supporting source(s) "
            f"and {len(contradicts)} contradicting source(s)."
        )
        return ClaimClassification.CONFLICTING, confidence, explanation

    # 4. Only neutral or inconclusive sources -> UNVERIFIED
    return (
        ClaimClassification.UNVERIFIED,
        0.50,
        "Available external sources mention related subjects but do not provide definitive confirmation or refutation.",
    )


def verify_claims(claim_texts: list[str]) -> list[dict[str, Any]]:
    """
    Verify a list of factual claims against external evidence.

    Returns:
        List of dicts:
        [
            {
                "classification": ClaimClassification,
                "confidence": float,
                "explanation": str,
                "sources": [
                    {
                        "title": str,
                        "url": str,
                        "domain": str,
                        "source_type": str,
                        "credibility_score": float,
                        "stance": str,
                        "stance_confidence": float,
                        "excerpt": str,
                    },
                    ...
                ]
            },
            ...
        ]
    """
    if not claim_texts:
        return []

    results = []

    for claim in claim_texts:
        logger.info("Verifying claim: '%s'", claim[:80])

        raw_evidence = retrieve_evidence(claim, max_results=4)
        processed_sources = []

        for ev in raw_evidence:
            snippet = ev.get("snippet", "")
            stance, stance_conf = determine_stance(claim, snippet)

            processed_sources.append({
                "title": ev.get("title", ""),
                "url": ev.get("url", ""),
                "domain": ev.get("domain", ""),
                "source_type": ev.get("source_type", "other").value if hasattr(ev.get("source_type"), "value") else str(ev.get("source_type", "other")),
                "credibility_score": float(ev.get("credibility_score", 0.5)),
                "stance": stance.value,
                "stance_confidence": float(stance_conf),
                "excerpt": snippet[:400],
            })

        classification, confidence, explanation = _synthesize_verdict(claim, processed_sources)

        results.append({
            "classification": classification,
            "confidence": confidence,
            "explanation": explanation,
            "sources": processed_sources,
        })

    logger.info("Completed verification for %d claim(s)", len(results))
    return results
