from web_search_mcp.urls import authority_score, clean_url, hostname, is_fetchable


def test_hostname_strips_www():
    assert hostname("https://www.example.com/x") == "example.com"
    assert hostname("https://example.com") == "example.com"


def test_clean_url_drops_tracking():
    assert (
        clean_url("https://site.com/a?utm_source=x&gclid=z&keep=1")
        == "https://site.com/a?keep=1"
    )
    assert clean_url("https://site.com/b?fbclid=abc&pk_campaign=news") == "https://site.com/b"


def test_clean_url_keeps_real_params():
    assert clean_url("https://site.com/c?q=real+query") == "https://site.com/c?q=real+query"


def test_clean_url_returns_invalid_as_is():
    assert clean_url("not a url") == "not a url"


def test_is_fetchable_blocks_private():
    assert is_fetchable("https://example.com/page")
    assert not is_fetchable("http://localhost:8080/x")
    assert not is_fetchable("http://192.168.1.1/x")
    assert not is_fetchable("http://127.0.0.1/x")
    assert not is_fetchable("ftp://example.com/x")
    assert not is_fetchable("not a url")


def test_authority_score():
    assert authority_score("edu.agency.gov") == 3
    assert authority_score("docs.example.org") == 3
    assert authority_score("example.org") == 1
    assert authority_score("example.com") == 0
