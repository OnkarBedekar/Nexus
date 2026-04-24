"""Stable identity strategy for canonical paper entities."""

from __future__ import annotations

import hashlib
import re

_WHITESPACE = re.compile(r"\s+")
_ARXIV = re.compile(r"(?:arxiv:)?(\d{4}\.\d{4,5})(?:v\d+)?", re.IGNORECASE)


def _norm(text: str) -> str:
    return _WHITESPACE.sub(" ", text.strip().lower())


def canonical_paper_id(
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    title: str = "",
    year: int | None = None,
) -> str:
    """Choose deterministic identity in order: DOI > arXiv > title/year hash."""
    if doi:
        basis = f"doi:{_norm(doi)}"
    elif arxiv_id:
        m = _ARXIV.search(arxiv_id)
        token = m.group(1) if m else arxiv_id
        basis = f"arxiv:{_norm(token)}"
    else:
        basis = f"title:{_norm(title)}|year:{year or 'unknown'}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
