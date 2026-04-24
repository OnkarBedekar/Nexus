from app.entity_identity import canonical_paper_id
from app.normalization import normalize_paper_record
from app.parsers import paper_to_entity_claims
from app.schemas import CanonicalPaper


def test_canonical_paper_id_prefers_doi() -> None:
    a = canonical_paper_id(
        doi="10.48550/arXiv.1706.03762",
        arxiv_id="1706.03762",
        title="Attention Is All You Need",
        year=2017,
    )
    b = canonical_paper_id(
        doi="10.48550/arXiv.1706.03762",
        title="attention is all you need",
        year=2017,
    )
    assert a == b


def test_normalize_paper_record_fields() -> None:
    paper = normalize_paper_record(
        {
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": ["Devlin", "Chang"],
            "year": 2018,
            "doi": "10.48550/arXiv.1810.04805",
            "keyFindings": ["Improves GLUE and SQuAD"],
            "references": ["Attention Is All You Need"],
            "citedBy": ["RoBERTa"],
        },
        source_url="https://arxiv.org/abs/1810.04805",
    )
    assert paper.paperId
    assert paper.title.startswith("BERT")
    assert paper.authors == ["Devlin", "Chang"]
    assert paper.year == 2018
    assert paper.sourceUrl == "https://arxiv.org/abs/1810.04805"


def test_normalize_key_findings_as_string_not_chars() -> None:
    """Models sometimes emit keyFindings as one paragraph string; must not split into letters."""
    paper = normalize_paper_record(
        {
            "title": "Example",
            "venue": "Goldman Sachs Insights",
            "year": 2024,
            "keyFindings": "Total addressable market expanded materially in 2024.",
        },
        source_url="https://example.com/r",
    )
    assert paper.keyFindings == ["Total addressable market expanded materially in 2024."]
    claims = paper_to_entity_claims(paper)
    assert claims == [
        "Published in Goldman Sachs Insights",
        "Year 2024",
        "Total addressable market expanded materially in 2024.",
    ]


def test_paper_to_entity_claims_repairs_single_char_findings() -> None:
    legacy = CanonicalPaper(
        paperId="p1",
        title="T",
        venue="Venue",
        year=2024,
        keyFindings=["T", "o", "t", "a", "l"],
    )
    claims = paper_to_entity_claims(legacy)
    assert "Total" in "".join(claims)
    assert all(len(c) > 1 or c.startswith("Published") or c.startswith("Year") for c in claims)
