"""Local fallback normalization into canonical paper entities."""

from __future__ import annotations

from typing import Any

from .entity_identity import canonical_paper_id
from .parsers import compact_text, parse_year
from .schemas import CanonicalPaper


def _coerce_flexible_string_list(value: Any, *, max_items: int) -> list[str]:
    """Normalize list fields from TinyFish/JSON: a bare string must not be iterated per-character."""
    if value is None:
        return []
    if isinstance(value, str):
        s = value.strip()
        return [s[:4000]] if s else []
    if isinstance(value, (list, tuple)):
        out: list[str] = []
        for x in value:
            sx = str(x).strip()
            if sx:
                out.append(sx[:4000])
            if len(out) >= max_items:
                break
        return out
    s = str(value).strip()
    return [s[:4000]] if s else []


def normalize_paper_record(record: dict[str, Any], *, source_url: str | None = None) -> CanonicalPaper:
    title = str(record.get("title") or record.get("name") or "Untitled paper").strip()
    authors_raw = record.get("authors") or []
    authors = [str(a).strip() for a in authors_raw if str(a).strip()]
    year = record.get("year")
    if not isinstance(year, int):
        year = parse_year(str(year) if year else title)
    doi = compact_text(record.get("doi"))
    arxiv_id = compact_text(record.get("arxivId"))

    paper_id = canonical_paper_id(
        doi=doi,
        arxiv_id=arxiv_id,
        title=title,
        year=year,
    )
    findings = _coerce_flexible_string_list(
        record.get("keyFindings") or record.get("claims"), max_items=8
    )
    refs = _coerce_flexible_string_list(record.get("references"), max_items=10)
    cited_by = _coerce_flexible_string_list(record.get("citedBy"), max_items=10)

    return CanonicalPaper(
        paperId=paper_id,
        title=title,
        authors=authors,
        year=year,
        venue=compact_text(record.get("venue")),
        doi=doi,
        arxivId=arxiv_id,
        citationCount=record.get("citationCount"),
        abstract=compact_text(record.get("abstract"), 1200),
        methodology=compact_text(record.get("methodology"), 600),
        keyFindings=findings,
        references=refs,
        citedBy=cited_by,
        sourceUrl=source_url or record.get("sourceUrl"),
        confidence=float(record.get("confidence", 0.75)),
    )
