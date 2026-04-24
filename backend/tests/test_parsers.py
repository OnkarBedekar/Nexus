from app.parsers import domain_allowed, parse_domains


def test_domain_allowed_subdomain() -> None:
    allowed = parse_domains("arxiv.org,semanticscholar.org")
    assert domain_allowed("https://www.semanticscholar.org/paper/foo", allowed)
    assert domain_allowed("https://arxiv.org/abs/1706.03762", allowed)
    assert not domain_allowed("https://example.com", allowed)
