"""
Natural Language Inference (NLI) & Stance Analysis module.

Determines whether an external evidence snippet SUPPORTS, CONTRADICTS,
or remains NEUTRAL toward a given factual claim.
"""
from __future__ import annotations

import logging
import re

from app.models.models import Stance

logger = logging.getLogger("fnad.ml.nli")

# ─────────────────────────────────────────────────────────────────────────────
# Contradiction / Debunking / Negation Patterns
# ─────────────────────────────────────────────────────────────────────────────

CONTRADICTION_CUES = [
    r"\b(false|fake|hoax|myth|fabricated|untrue|unfounded|baseless|debunked|disproven)\b",
    r"\b(no\s+evidence\s+(to\s+support|that|of)|contrary\s+to\s+(claims|reports))\b",
    r"\b(refuted|denied\s+(the\s+claim|that)|rejected\s+claims|incorrectly\s+claimed)\b",
    r"\b(misleading|distorted|out\s+of\s+context|falsely\s+claimed)\b",
    r"\b(did\s+not\s+(happen|occur|announce|sign|pass|approve|drop|increase))\b",
    r"\b(never\s+(happened|occurred|announced|signed|passed|approved))\b",
    r"\b(not\s+true|not\s+accurate|inaccurate|wrongly\s+reported)\b",
]

CONFIRMATION_CUES = [
    r"\b(confirmed|announced|stated|reported|verified|concluded|proven|demonstrated)\b",
    r"\b(signed\s+into\s+law|officially\s+enacted|passed\s+the|authorized|approved)\b",
    r"\b(study\s+found|data\s+shows|findings\s+indicate|official\s+statement)\b",
    r"\b(true|accurate|authentic|substantiated|corroborated)\b",
]

STOPWORDS = {
    "the", "a", "an", "is", "was", "are", "were", "and", "or", "to", "in", "on", "at",
    "by", "for", "with", "about", "that", "this", "it", "from", "as", "of"
}

COMMON_ACRONYMS = {
    "who": "world health organization",
    "cdc": "centers for disease control",
    "un": "united nations",
    "fda": "food and drug administration",
    "nasa": "national aeronautics and space administration",
    "fbi": "federal bureau of investigation",
    "nato": "north atlantic treaty organization",
    "eu": "european union",
}


def _stem(word: str) -> str:
    """Basic rule-based suffix stemming for common English inflection."""
    w = word.lower()
    for suffix in ("ing", "tion", "ed", "es", "ly", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 3:
            return w[:-len(suffix)]
    return w


def _extract_keywords(text: str) -> set[str]:
    """Extract significant alphabetic and numerical terms with basic stemming and acronym expansion."""
    clean = re.sub(r"[^\w\s\%\$]", " ", text.lower())
    words = clean.split()

    # Expand acronyms if present
    expanded_words = []
    for w in words:
        expanded_words.append(w)
        if w in COMMON_ACRONYMS:
            expanded_words.extend(COMMON_ACRONYMS[w].split())

    keywords = set()
    for w in expanded_words:
        if w not in STOPWORDS and len(w) > 2:
            keywords.add(w)
            keywords.add(_stem(w))

    return keywords


def _extract_numbers_and_years(text: str) -> set[str]:
    """Extract digits, percentages, and dollar figures."""
    return set(re.findall(r"\b\d+(?:\.\d+)?%?|\$\d+(?:\.\d+)?", text))


def determine_stance(claim: str, evidence: str) -> tuple[Stance, float]:
    """
    Evaluate the semantic and logical relationship between claim and evidence.

    Returns:
        (stance: Stance, confidence: float)
    """
    if not claim or not evidence:
        return Stance.NEUTRAL, 0.50

    claim_words = _extract_keywords(claim)
    evidence_words = _extract_keywords(evidence)

    # 1. Relevance check: Overlap of non-stopwords
    shared_words = claim_words & evidence_words
    overlap_ratio = len(shared_words) / max(1, len(claim_words))

    if overlap_ratio < 0.15:
        # Irrelevant or insufficient lexical overlap
        return Stance.NEUTRAL, 0.50

    ev_lower = evidence.lower()

    # 2. Check for explicit contradiction or debunking cues
    for pat in CONTRADICTION_CUES:
        if re.search(pat, ev_lower):
            conf = min(0.95, round(0.65 + overlap_ratio * 0.30, 2))
            return Stance.CONTRADICTS, conf

    # 3. Check for numerical discrepancy vs agreement
    claim_nums = _extract_numbers_and_years(claim)
    ev_nums = _extract_numbers_and_years(evidence)

    if claim_nums and ev_nums:
        # If numbers match directly with high overlap
        if claim_nums.issubset(ev_nums) and overlap_ratio >= 0.35:
            conf = min(0.95, round(0.70 + overlap_ratio * 0.25, 2))
            return Stance.SUPPORTS, conf
        # If numbers explicitly mismatch
        elif not (claim_nums & ev_nums) and overlap_ratio >= 0.50:
            # Different numbers discussed for the same topic
            return Stance.CONTRADICTS, 0.70

    # 4. Check for confirmation cues
    for pat in CONFIRMATION_CUES:
        if re.search(pat, ev_lower) and overlap_ratio >= 0.30:
            conf = min(0.92, round(0.60 + overlap_ratio * 0.30, 2))
            return Stance.SUPPORTS, conf

    # 5. Moderate overlap without decisive confirmation or contradiction
    if overlap_ratio >= 0.40:
        return Stance.SUPPORTS, round(0.55 + overlap_ratio * 0.20, 2)

    return Stance.NEUTRAL, 0.55
