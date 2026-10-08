"""
Claim Extraction & Check-Worthiness Analysis module.

Extracts atomic, verifiable factual claims from transcripts, filtering out
conversational noise, greetings, opinions, questions, filler, and calls-to-action,
and aligns each claim with audio playback timestamps (start_time, end_time).
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings

logger = logging.getLogger("fnad.ml.claim_extraction")

# ─────────────────────────────────────────────────────────────────────────────
# Noise, Greeting, and Non-Factual Patterns
# ─────────────────────────────────────────────────────────────────────────────

GREETING_PATTERNS = [
    r"^(hello|hi|hey|good\s+(morning|afternoon|evening|day)|welcome|greetings)\b",
    r"\b(welcome\s+back|thanks?\s+for\s+(watching|listening|tuning\s+in))\b",
    r"\b(see\s+you\s+(later|next\s+time|tomorrow)|goodbye|bye\s+bye|have\s+a\s+great\s+day)\b",
    r"\b(subscribe|like\s+and\s+subscribe|hit\s+the\s+bell|leave\s+a\s+comment|follow\s+us)\b",
    r"\b(don't\s+forget\s+to\s+subscribe|click\s+the\s+link\s+in\s+the\s+description)\b",
    r"^(thank\s+you\s+very\s+much|thanks\s+everyone|all\s+right\s+guys)\b",
]

OPINION_PREF_PATTERNS = [
    r"^(i\s+(think|feel|believe|personally\s+feel|guess|suppose|bet))\b",
    r"^(in\s+my\s+(opinion|view|humble\s+opinion))\b",
    r"^(it\s+seems\s+to\s+me|to\s+be\s+honest|honestly\s+speaking)\b",
    r"^(i\s+really\s+(love|hate|enjoy|like|dislike))\b",
]

QUESTION_PATTERNS = [
    r"\?$",
    r"^(what|why|how|where|when|who|which|is\s+it\s+possible|do\s+you\s+think|can\s+you\s+believe)\b",
]

FILLER_ONLY_PATTERNS = [
    r"^(um+|uh+|ah+|er+|oh+|yeah|yep|nope|okay|ok|well|like|you\s+know|right)$",
]

# ─────────────────────────────────────────────────────────────────────────────
# Positive Check-Worthiness Indicators
# ─────────────────────────────────────────────────────────────────────────────

FACTUAL_VERB_PATTERNS = [
    r"\b(announced|stated|reported|confirmed|declared|revealed|discovered|invented)\b",
    r"\b(signed|passed|enacted|banned|approved|rejected|vetoed|authorized)\b",
    r"\b(increased|decreased|rose|fell|dropped|surged|doubled|tripled|plummeted)\b",
    r"\b(died|killed|injured|infected|diagnosed|tested\s+positive|recovered)\b",
    r"\b(launched|deployed|built|constructed|developed|patented|manufactured)\b",
    r"\b(elected|resigned|appointed|nominated|fired|dismissed|arrested|convicted)\b",
    r"\b(published|concluded|found\s+that|proven\s+to|demonstrated\s+that)\b",
    r"\b(spent|funded|invested|cost|awarded|allocated|stole|embezzled)\b",
]

QUANTITY_PATTERNS = [
    r"\b\d+(\.\d+)?\s*(%|percent|percentage)\b",
    r"(\$|€|£|₹)\s*\d+(\.\d+)?(\s*(million|billion|trillion|thousand))?\b",
    r"\b\d+(\.\d+)?\s*(million|billion|trillion|thousand|hundred)\b",
    r"\b(in|by|since|during)\s+(19\d\d|20\d\d)\b",
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(,\s*\d{4})?\b",
    r"\b\d+\s*(people|cases|deaths|patients|troops|dollars|euros|tonnes|tons|miles|kilometers|km)\b",
]

ENTITY_PATTERNS = [
    r"\b(who|un|cdc|fda|nasa|nato|fbi|cia|imf|eu|epa|nih|supreme\s+court)\b",
    r"\b(president|prime\s+minister|senator|governor|mayor|chancellor|minister)\b",
    r"\b(government|parliament|congress|white\s+house|pentagon|kremlin)\b",
    r"\b(university|hospital|study|researchers?|scientists?|officials?)\b",
]


def _clean_sentence(text: str) -> str:
    """Normalize whitespace and remove stray quotes."""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip("\"'“”‘’")
    return text


def split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into distinct sentences, respecting abbreviations
    (e.g., 'U.S.', 'Dr.', 'Mr.') and decimals.
    """
    if not text:
        return []

    # Protect common abbreviations and acronyms
    protected = text
    protected = re.sub(r"\bU\.S\.", "U_S_", protected)
    protected = re.sub(r"\bU\.K\.", "U_K_", protected)
    protected = re.sub(r"\bU\.N\.", "U_N_", protected)
    protected = re.sub(r"\b([A-Z])\.", r"\1_", protected)
    protected = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Gov|Sen|Rep)\.", r"\1_", protected, flags=re.IGNORECASE)
    protected = re.sub(r"(\d+)\.(\d+)", r"\1_DOT_\2", protected)

    # Split on terminal punctuation
    raw_sentences = re.split(r"(?<=[.!?])\s+", protected)

    clean_sentences = []
    for s in raw_sentences:
        s = s.replace("U_S_", "U.S.")
        s = s.replace("U_K_", "U.K.")
        s = s.replace("U_N_", "U.N.")
        s = re.sub(r"\b([A-Z])_", r"\1.", s)
        s = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Gov|Sen|Rep)_", r"\1.", s, flags=re.IGNORECASE)
        s = s.replace("_DOT_", ".")
        s = _clean_sentence(s)
        if s:
            clean_sentences.append(s)

    return clean_sentences


def compute_check_worthiness(sentence: str) -> tuple[bool, float, list[str]]:
    """
    Evaluate whether a sentence constitutes a check-worthy factual claim.

    Returns:
        (is_claim: bool, score: float, reasons: list[str])
    """
    lower = sentence.lower()
    words = sentence.split()

    # Rule 1: Length check (reject trivially short utterances)
    if len(words) < 4:
        return False, 0.0, ["Too short (< 4 words)"]

    # Rule 2: Exclude pure fillers
    for pat in FILLER_ONLY_PATTERNS:
        if re.match(pat, lower.strip(" .!")):
            return False, 0.0, ["Filler phrase"]

    # Rule 3: Exclude greetings and channel call-to-actions
    for pat in GREETING_PATTERNS:
        if re.search(pat, lower):
            return False, 0.0, ["Greeting or call-to-action"]

    # Rule 4: Exclude pure questions (unless rhetorical claim)
    for pat in QUESTION_PATTERNS:
        if re.search(pat, lower):
            return False, 0.0, ["Question / interrogative"]

    # Rule 5: Heavy penalty for pure subjective opinions
    is_opinion = False
    for pat in OPINION_PREF_PATTERNS:
        if re.search(pat, lower):
            is_opinion = True
            break

    score = 0.2  # Base prior for declarative sentences
    reasons = ["Declarative sentence structure"]

    # Boost: Factual reporting verbs
    for pat in FACTUAL_VERB_PATTERNS:
        if re.search(pat, lower):
            score += 0.25
            reasons.append("Contains factual event/action verb")
            break

    # Boost: Quantities, numbers, dates
    for pat in QUANTITY_PATTERNS:
        if re.search(pat, lower):
            score += 0.25
            reasons.append("Contains verifiable quantity/statistic/date")
            break

    # Boost: Named entities / institutions
    for pat in ENTITY_PATTERNS:
        if re.search(pat, lower):
            score += 0.20
            reasons.append("References identifiable institution or official")
            break

    # Boost: Specificity / length (moderate sentences carry more specific claims)
    if 8 <= len(words) <= 35:
        score += 0.10

    if is_opinion:
        score -= 0.35
        reasons.append("Subjective opinion penalty")

    score = max(0.0, min(1.0, round(score, 2)))
    is_claim = score >= 0.40

    return is_claim, score, reasons


def align_timestamps(sentence: str, segments: list[dict[str, Any]]) -> tuple[float | None, float | None]:
    """
    Map an extracted sentence back to its audio playback window (start_time, end_time)
    using Whisper transcription segments.
    """
    if not segments:
        return None, None

    sent_clean = re.sub(r"[^\w\s]", " ", sentence.lower())
    sent_words = [w for w in sent_clean.split() if w]

    if not sent_words:
        return segments[0].get("start"), segments[-1].get("end")

    # Filter out ubiquitous single stopwords when finding sentence start
    stopwords = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or", "is", "it", "that", "this"}
    significant_words = [w for w in sent_words if w not in stopwords]
    anchor_words = significant_words[:3] if significant_words else sent_words[:2]

    # Find the segment that best matches the start of the sentence
    best_start = None
    best_end = None
    max_overlap = -1
    best_seg = None

    for seg in segments:
        seg_text = seg.get("text", "").lower()
        seg_clean = re.sub(r"[^\w\s]", " ", seg_text)
        seg_words = set(seg_clean.split())

        # Check if anchor words appear in this segment
        anchors_in_seg = sum(1 for w in anchor_words if w in seg_words)
        if best_start is None and (anchors_in_seg >= max(1, len(anchor_words) // 2)):
            best_start = seg.get("start")

        # Track overlap for start/end boundaries
        overlap = len(set(sent_words) & seg_words)
        if overlap > 0:
            best_end = seg.get("end")
            if overlap > max_overlap:
                max_overlap = overlap
                best_seg = seg

    # If anchor matching didn't trigger, use the segment with highest overlap
    if best_start is None and best_seg is not None:
        best_start = best_seg.get("start")

    # Fallback to entire range if still None
    if best_start is None and segments:
        best_start = segments[0].get("start")
    if best_end is None and segments:
        best_end = segments[-1].get("end")

    return best_start, best_end


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """Compute word-level Jaccard similarity for deduplication."""
    set_a = set(re.sub(r"[^\w\s]", "", text_a.lower()).split())
    set_b = set(re.sub(r"[^\w\s]", "", text_b.lower()).split())
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def deduplicate_claims(claims: list[dict[str, Any]], threshold: float = 0.70) -> list[dict[str, Any]]:
    """Remove redundant or near-duplicate claims while preserving the best instance."""
    unique_claims: list[dict[str, Any]] = []

    for candidate in claims:
        is_dup = False
        for kept in unique_claims:
            sim = _jaccard_similarity(candidate["text"], kept["text"])
            if sim >= threshold:
                is_dup = True
                # If candidate has higher score, replace
                if candidate.get("confidence", 0) > kept.get("confidence", 0):
                    kept["text"] = candidate["text"]
                    kept["confidence"] = candidate["confidence"]
                    kept["start_time"] = candidate["start_time"]
                    kept["end_time"] = candidate["end_time"]
                break

        if not is_dup:
            unique_claims.append(candidate)

    return unique_claims


def extract_claims(
    full_text: str,
    segments: list[dict[str, Any]] | None = None,
    max_claims: int = 15,
) -> list[dict[str, Any]]:
    """
    Extract verifiable factual claims from a transcript and map to timestamps.

    Parameters:
        full_text: The complete transcript text.
        segments: Timestamped segment list from speech_to_text.
        max_claims: Maximum number of claims to return.

    Returns:
        List of claim dicts:
        [
            {
                "text": str,
                "start_time": float | None,
                "end_time": float | None,
                "confidence": float,
                "reasons": list[str],
            },
            ...
        ]
    """
    if not full_text or not full_text.strip():
        logger.info("extract_claims: Empty transcript provided, returning 0 claims.")
        return []

    segments = segments or []
    sentences = split_into_sentences(full_text)
    logger.debug("Split transcript into %d sentence(s)", len(sentences))

    candidate_claims: list[dict[str, Any]] = []

    for sentence in sentences:
        is_claim, score, reasons = compute_check_worthiness(sentence)
        if is_claim:
            start_t, end_t = align_timestamps(sentence, segments)
            candidate_claims.append({
                "text": sentence,
                "start_time": round(float(start_t), 2) if start_t is not None else None,
                "end_time": round(float(end_t), 2) if end_t is not None else None,
                "confidence": score,
                "reasons": reasons,
            })

    # Fallback: If no candidate passed the strict threshold but the text contains
    # a declarative sentence (> 5 words), take the highest scoring sentence
    if not candidate_claims and sentences:
        scored = []
        for s in sentences:
            _, s_score, s_reasons = compute_check_worthiness(s)
            start_t, end_t = align_timestamps(s, segments)
            if len(s.split()) >= 4:
                scored.append({
                    "text": s,
                    "start_time": round(float(start_t), 2) if start_t is not None else None,
                    "end_time": round(float(end_t), 2) if end_t is not None else None,
                    "confidence": s_score,
                    "reasons": s_reasons,
                })
        if scored:
            scored.sort(key=lambda x: x["confidence"], reverse=True)
            candidate_claims.append(scored[0])

    # Deduplicate repetitive assertions
    deduped = deduplicate_claims(candidate_claims)

    # Sort primarily by chronological occurrence (order in speech), capped at max_claims
    final_claims = deduped[:max_claims]

    logger.info(
        "Extracted %d claim(s) from %d candidate sentence(s)",
        len(final_claims), len(sentences)
    )

    return final_claims
