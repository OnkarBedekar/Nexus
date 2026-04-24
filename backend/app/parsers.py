"""Parsing helpers for paper-centric extraction and traversal."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from .schemas import CanonicalPaper

_YEAR = re.compile(r"\b(19|20)\d{2}\b")


def parse_domains(csv_domains: str) -> list[str]:
    return [d.strip().lower() for d in csv_domains.split(",") if d.strip()]


def domain_allowed(url: str, allowed_domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == dom or host.endswith(f".{dom}") for dom in allowed_domains)


def compact_text(value: str | None, max_len: int = 300) -> str | None:
    if not value:
        return None
    text = " ".join(value.split())
    return text[:max_len]


def parse_year(text: str | None) -> int | None:
    if not text:
        return None
    m = _YEAR.search(text)
    return int(m.group(0)) if m else None


def source_priority(url: str) -> int:
    host = (urlparse(url).hostname or "").lower()
    if "arxiv.org" in host:
        return 5
    if "semanticscholar.org" in host:
        return 4
    if "pubmed" in host:
        return 3
    if "scholar.google.com" in host:
        return 2
    if ".edu" in host or "lab" in host:
        return 1
    return 0


def _key_findings_for_claims(kf: list[str]) -> list[str]:
    """Repair legacy papers where keyFindings was stored as one char per list element."""
    if not kf:
        return []
    if len(kf) >= 3 and all(isinstance(x, str) and len(x) == 1 for x in kf):
        merged = "".join(kf).strip()
        return [merged] if merged else []
    return [x for x in kf if isinstance(x, str) and x.strip()]


def paper_to_entity_claims(paper: CanonicalPaper) -> list[str]:
    claims: list[str] = []
    if paper.venue:
        claims.append(f"Published in {paper.venue}")
    if paper.year:
        claims.append(f"Year {paper.year}")
    if paper.methodology:
        claims.append(f"Methodology: {paper.methodology}")
    claims.extend(_key_findings_for_claims(paper.keyFindings)[:3])
    return claims[:5]
