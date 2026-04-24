"""Deterministic IDs for entities and relationships.

Two agents extracting the same canonical name for the same type must
produce the same ID so dedup works across the pipeline.
"""

from __future__ import annotations

import hashlib
import re


_WHITESPACE_RE = re.compile(r"\s+")


def _canonicalize(name: str) -> str:
    """Lowercase, collapse whitespace, strip - good enough for hackathon dedup."""
    return _WHITESPACE_RE.sub(" ", name.strip().lower())


def entity_id(entity_type: str, name: str) -> str:
    """Stable 16-char hex ID for (type, canonical-name)."""
    basis = f"{entity_type.lower()}:{_canonicalize(name)}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]


def relationship_id(from_id: str, to_id: str, predicate: str) -> str:
    """Stable ID for a typed edge."""
    basis = f"{from_id}:{predicate.lower()}:{to_id}"
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]
