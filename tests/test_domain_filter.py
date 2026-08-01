from web_search_mcp.urls import matches_domain_filter


def test_matches_domain_filter():
    url = "https://docs.python.org/3/library/unittest.html"

    # Include matching
    assert matches_domain_filter(url, include_domains=["python.org"]) is True
    assert matches_domain_filter(url, include_domains=["github.com"]) is False

    # Exclude matching
    assert matches_domain_filter(url, exclude_domains=["python.org"]) is False
    assert matches_domain_filter(url, exclude_domains=["pinterest.com"]) is True

    # Combined
    assert (
        matches_domain_filter(
            url, include_domains=["python.org"], exclude_domains=["pinterest.com"]
        )
        is True
    )
