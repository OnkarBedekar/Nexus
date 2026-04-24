from app.entity_identity import canonical_paper_id
from app.normalization import normalize_paper_record


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
