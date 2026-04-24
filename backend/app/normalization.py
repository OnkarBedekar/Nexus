"""Local fallback normalization into canonical paper entities."""

from __future__ import annotations

from typing import Any

from .entity_identity import canonical_paper_id
from .parsers import compact_text, parse_year
from .schemas import CanonicalPaper


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
    findings = record.get("keyFindings") or record.get("claims") or []
    refs = record.get("references") or []
    cited_by = record.get("citedBy") or []

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
        keyFindings=[str(x) for x in findings[:8]],
        references=[str(x) for x in refs[:10]],
        citedBy=[str(x) for x in cited_by[:10]],
        sourceUrl=source_url or record.get("sourceUrl"),
        confidence=float(record.get("confidence", 0.75)),
    )
