from web_search_mcp.config import Settings
from web_search_mcp.http import Http
from web_search_mcp.providers.exa import ExaProvider
from web_search_mcp.providers.searxng import SearXNGProvider


def test_provider_availability():
    s1 = Settings(searxng_base_url="https://searx.example.com", exa_api_key="")
    http = Http(s1)

    searx = SearXNGProvider(s1, http)
    exa = ExaProvider(s1, http)

    assert searx.available() is True
    assert exa.available() is False

    s2 = Settings(searxng_base_url="", exa_api_key="test-key")
    searx2 = SearXNGProvider(s2, http)
    exa2 = ExaProvider(s2, http)

    assert searx2.available() is False
    assert exa2.available() is True
