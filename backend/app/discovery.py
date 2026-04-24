"""Phase-1: discover a bounded list of public URLs for a research topic.

Uses Brave Search API when BRAVE_SEARCH_API is set; otherwise scrapes
DuckDuckGo HTML with httpx. Falls back to seed URLs or Wikipedia if discovery
yields no usable links.
"""

from __future__ import annotations

import logging
import re
from html import unescape
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .config import Settings, get_settings

log = logging.getLogger(__name__)

# Skip obvious non-content hosts for research extraction.
_DEFAULT_BLOCKLIST: frozenset[str] = frozenset(
    {
        "duckduckgo.com",
        "www.duckduckgo.com",
        "google.com",
        "www.google.com",
        "bing.com",
        "www.bing.com",
        "facebook.com",
        "x.com",
        "twitter.com",
    }
)

_RESULT_A_RE = re.compile(
    r'class="result__a"[^>]+href="([^"]+)"',
    re.IGNORECASE,
)
_UDDG_RE = re.compile(r"uddg=([^&\"]+)")


def _host_allowed(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
        if not host:
            return False
        for bad in _DEFAULT_BLOCKLIST:
            if host == bad or host.endswith(f".{bad}"):
                return False
        return True
    except Exception:
        return False


def _normalize_ddg_redirect(url: str) -> str:
    u = unescape(url.strip())
    if "duckduckgo.com/l/" in u or u.startswith("//duckduckgo.com/l/"):
        try:
            qs = parse_qs(urlparse("https:" + u if u.startswith("//") else u).query)
            if "uddg" in qs:
                return unquote(qs["uddg"][0])
        except Exception:
            pass
    return u


async def _brave_search(
    query: str, max_results: int, api_key: str, timeout: float = 20.0
) -> list[dict[str, Any]]:
    """Brave Web Search; returns {url, title} dicts."""
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": min(20, max(1, max_results))},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
        )
        r.raise_for_status()
        data = r.json()
        for item in (data.get("web", {}) or {}).get("results", []):
            u = (item or {}).get("url")
            if not u or not _host_allowed(u):
                continue
            out.append(
                {
                    "url": u,
                    "title": (item or {}).get("title"),
                }
            )
            if len(out) >= max_results:
                break
    return out


async def _duckduckgo_html(
    query: str, max_results: int, timeout: float = 25.0
) -> list[dict[str, Any]]:
    """Scrape html.duckduckgo.com; returns {url, title} dicts."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=timeout, headers=headers
    ) as client:
        r = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
        )
        r.raise_for_status()
        text = r.text
    for m in _RESULT_A_RE.finditer(text):
        u = _normalize_ddg_redirect(m.group(1))
        if u.startswith("http") and _host_allowed(u):
            out.append({"url": u, "title": None})
            if len(out) >= max_results:
                return out
    if len(out) < max_results:
        for m in _UDDG_RE.finditer(text):
            u = unquote(m.group(1).replace("+", " "))
            if u.startswith("http") and _host_allowed(u):
                if not any(x["url"] == u for x in out):
                    out.append({"url": u, "title": None})
                if len(out) >= max_results:
                    break
    return out[:max_results]


def _dedupe_preserve_order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        u = item.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(item)
    return out


async def discover_web_urls(
    topic: str,
    max_results: int,
    *,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return up to `max_results` {url, title?} for use as agent entry points."""
    s = settings or get_settings()
    n = min(max(1, max_results), 25)
    results: list[dict[str, Any]] = []
    if s.brave_search_api:
        try:
            results = await _brave_search(topic, n, s.brave_search_api)
            log.info("Brave discovery returned %d URLs", len(results))
        except Exception as exc:  # pragma: no cover - network
            log.warning("Brave discovery failed: %s; falling back to DuckDuckGo", exc)
    if not results and s.enable_duckduckgo_discovery:
        try:
            results = await _duckduckgo_html(topic, n)
            log.info("DuckDuckGo discovery returned %d URLs", len(results))
        except Exception as exc:  # pragma: no cover - network
            log.warning("DuckDuckGo discovery failed: %s", exc)
    return _dedupe_preserve_order(results)[:n]
