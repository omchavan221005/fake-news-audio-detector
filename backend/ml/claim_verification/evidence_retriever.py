"""
Evidence Retrieval module for automated fact-checking.

Dispatches search queries to Serper (Google Search), Tavily, or Wikipedia API
(zero-key fallback) and normalizes evidence snippets with source credibility metadata.
"""
from __future__ import annotations

import html
import logging
import re
from typing import Any

import httpx

from app.config import settings
from app.models.models import SourceType
from ml.claim_verification.domain_credibility import classify_domain

import threading

logger = logging.getLogger("fnad.ml.evidence")

REQUEST_TIMEOUT_SECONDS = 5.0
USER_AGENT = "FakeNewsAudioDetector/1.0 (+https://github.com/example/fake-news-audio-detector)"

# In-memory query result cache for Phase 11 performance optimization
_CACHE_LOCK = threading.Lock()
_EVIDENCE_CACHE: dict[str, list[dict[str, Any]]] = {}
_MAX_CACHE_SIZE = 500


def clear_evidence_cache():
    """Clear in-memory evidence cache."""
    with _CACHE_LOCK:
        _EVIDENCE_CACHE.clear()


def generate_search_query(claim_text: str) -> str:
    """Extract clean keywords and remove leading/trailing noise for search engines."""
    text = re.sub(r"^(it\s+was\s+reported\s+that|officials\s+stated\s+that|according\s+to\s+reports,?\s*)", "", claim_text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s\$\%\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    words = text.split()
    # Limit to 12 most salient terms for search query efficiency
    return " ".join(words[:12])


def _search_wikipedia(query: str, max_results: int = 3) -> list[dict[str, Any]]:
    """Retrieve evidence snippets from Wikipedia API (requires no API key)."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": max_results,
        "utf8": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        resp = client.get(url, params=params, headers=headers)
        if resp.status_code != 200:
            logger.warning("Wikipedia API returned status %d", resp.status_code)
            return []

        data = resp.json()
        search_hits = data.get("query", {}).get("search", [])

        results = []
        for hit in search_hits:
            title = hit.get("title", "")
            raw_snippet = hit.get("snippet", "")
            clean_snippet = re.sub(r"<[^>]+>", "", raw_snippet)
            clean_snippet = html.unescape(clean_snippet).strip()

            page_id = hit.get("pageid")
            page_url = f"https://en.wikipedia.org/?curid={page_id}" if page_id else "https://en.wikipedia.org"

            src_type, cred_score, norm_domain = classify_domain("en.wikipedia.org")

            results.append({
                "title": f"Wikipedia: {title}",
                "url": page_url,
                "snippet": clean_snippet,
                "domain": norm_domain,
                "source_type": src_type,
                "credibility_score": cred_score,
            })
        return results


def _search_serper(query: str, api_key: str, max_results: int = 4) -> list[dict[str, Any]]:
    """Retrieve evidence from Google Search via Serper.dev API."""
    url = "https://google.serper.dev/search"
    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }
    payload = {"q": query, "num": max_results}

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.warning("Serper API returned status %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        results = []
        for item in data.get("organic", [])[:max_results]:
            item_url = item.get("link", "")
            src_type, cred_score, norm_domain = classify_domain(item_url)
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("snippet", ""),
                "domain": norm_domain,
                "source_type": src_type,
                "credibility_score": cred_score,
            })
        return results


def _search_tavily(query: str, api_key: str, max_results: int = 4) -> list[dict[str, Any]]:
    """Retrieve evidence from Tavily Search API."""
    url = "https://api.tavily.com/search"
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        resp = client.post(url, json=payload, headers=headers)
        if resp.status_code != 200:
            logger.warning("Tavily API returned status %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        results = []
        for item in data.get("results", [])[:max_results]:
            item_url = item.get("url", "")
            src_type, cred_score, norm_domain = classify_domain(item_url)
            results.append({
                "title": item.get("title", ""),
                "url": item_url,
                "snippet": item.get("content", ""),
                "domain": norm_domain,
                "source_type": src_type,
                "credibility_score": cred_score,
            })
        return results


def retrieve_evidence(claim_text: str, max_results: int = 4) -> list[dict[str, Any]]:
    """
    Retrieve external evidence snippets for a claim.

    Dispatches to Serper, Tavily, or Wikipedia depending on configuration.
    Network failures or timeouts return an empty list gracefully.
    """
    query = generate_search_query(claim_text)
    if not query:
        return []

    cache_key = f"{query}::{max_results}"
    with _CACHE_LOCK:
        if cache_key in _EVIDENCE_CACHE:
            logger.debug("Evidence cache hit for query: '%s'", query)
            return _EVIDENCE_CACHE[cache_key]

    provider = (settings.search_api_provider or "").lower()
    api_key = settings.search_api_key

    logger.info("Retrieving evidence for query: '%s' (provider=%s)", query, provider or "wikipedia")

    evidence = []
    try:
        if provider == "serper" and api_key:
            evidence = _search_serper(query, api_key, max_results)
            if not evidence:
                evidence = _search_wikipedia(query, max_results)
        elif provider == "tavily" and api_key:
            evidence = _search_tavily(query, api_key, max_results)
            if not evidence:
                evidence = _search_wikipedia(query, max_results)
        else:
            # Default fallback: Wikipedia
            evidence = _search_wikipedia(query, max_results)

    except Exception as exc:
        logger.warning("Evidence retrieval failed for '%s': %s", query, exc)
        evidence = []

    with _CACHE_LOCK:
        if len(_EVIDENCE_CACHE) >= _MAX_CACHE_SIZE:
            _EVIDENCE_CACHE.pop(next(iter(_EVIDENCE_CACHE)))
        _EVIDENCE_CACHE[cache_key] = evidence

    return evidence
