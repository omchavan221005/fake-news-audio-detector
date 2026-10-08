"""
Domain Credibility & Source Categorization module.

Analyzes evidence URLs, extracts domain names, assigns SourceType
(government, academic, news, primary, other), and determines credibility scores.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from app.models.models import SourceType

# ─────────────────────────────────────────────────────────────────────────────
# Known Curated Domains and Reputation Scores
# ─────────────────────────────────────────────────────────────────────────────

GOVERNMENT_DOMAINS = {
    "who.int": 0.98,
    "un.org": 0.96,
    "cdc.gov": 0.98,
    "nih.gov": 0.98,
    "nasa.gov": 0.98,
    "fda.gov": 0.98,
    "state.gov": 0.95,
    "whitehouse.gov": 0.95,
    "europa.eu": 0.95,
    "gov.uk": 0.96,
    "nato.int": 0.94,
    "imf.org": 0.95,
    "worldbank.org": 0.95,
}

ACADEMIC_DOMAINS = {
    "nature.com": 0.98,
    "science.org": 0.98,
    "thelancet.com": 0.98,
    "nejm.org": 0.98,
    "cell.com": 0.96,
    "sciencedirect.com": 0.94,
    "pnas.org": 0.96,
    "arxiv.org": 0.90,
    "jstor.org": 0.92,
    "bmj.com": 0.96,
}

PRIMARY_FACTCHECK_DOMAINS = {
    "snopes.com": 0.95,
    "politifact.com": 0.95,
    "factcheck.org": 0.95,
    "fullfact.org": 0.94,
    "leadstories.com": 0.92,
    "wikipedia.org": 0.88,
}

HIGH_REPUTATION_NEWS_DOMAINS = {
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.92,
    "bbc.co.uk": 0.92,
    "theguardian.com": 0.88,
    "nytimes.com": 0.90,
    "washingtonpost.com": 0.89,
    "wsj.com": 0.91,
    "bloomberg.com": 0.92,
    "npr.org": 0.91,
    "afp.com": 0.94,
    "ft.com": 0.92,
    "economist.com": 0.92,
    "time.com": 0.86,
    "dw.com": 0.89,
    "france24.com": 0.88,
    "aljazeera.com": 0.85,
    "cnn.com": 0.82,
    "forbes.com": 0.83,
}

LOW_CREDIBILITY_OR_SATIRE_DOMAINS = {
    "theonion.com": 0.10,
    "babylonbee.com": 0.10,
    "worldnewsdailyreport.com": 0.05,
    "infowars.com": 0.15,
    "beforeitsnews.com": 0.10,
    "naturalnews.com": 0.15,
}


def extract_domain(url_or_domain: str) -> str:
    """Extract a normalized root domain from a URL or raw domain string."""
    if not url_or_domain:
        return ""

    raw = url_or_domain.strip().lower()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw

    try:
        parsed = urlparse(raw)
        hostname = parsed.hostname or ""
    except Exception:
        hostname = raw

    hostname = re.sub(r"^www\.", "", hostname)
    return hostname


def classify_domain(url_or_domain: str) -> tuple[SourceType, float, str]:
    """
    Classify a URL or domain into SourceType and assign a credibility score (0.0 – 1.0).

    Returns:
        (source_type: SourceType, credibility_score: float, normalized_domain: str)
    """
    domain = extract_domain(url_or_domain)
    if not domain:
        return SourceType.OTHER, 0.50, ""

    # Check exact match or parent domain
    for d, score in GOVERNMENT_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return SourceType.GOVERNMENT, score, domain

    for d, score in ACADEMIC_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return SourceType.ACADEMIC, score, domain

    for d, score in PRIMARY_FACTCHECK_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return SourceType.PRIMARY, score, domain

    for d, score in HIGH_REPUTATION_NEWS_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return SourceType.NEWS, score, domain

    for d, score in LOW_CREDIBILITY_OR_SATIRE_DOMAINS.items():
        if domain == d or domain.endswith("." + d):
            return SourceType.OTHER, score, domain

    # Suffix heuristics
    if re.search(r"\.gov(\.[a-z]{2})?$", domain) or domain.endswith(".mil"):
        return SourceType.GOVERNMENT, 0.95, domain

    if re.search(r"\.edu(\.[a-z]{2})?$", domain) or re.search(r"\.ac\.[a-z]{2}$", domain):
        return SourceType.ACADEMIC, 0.92, domain

    # Default general web domain
    return SourceType.OTHER, 0.55, domain
