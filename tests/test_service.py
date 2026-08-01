from web_search_mcp.cache import MemoryTTLCache
from web_search_mcp.config import Settings
from web_search_mcp.service import WebSearchService

PAYLOAD = {
    "web": {
        "results": [
            {"title": "A", "url": "https://a.com/1", "description": "d1"},
            {"title": "A2", "url": "https://a.com/2", "description": "d2"},
            {"title": "B", "url": "https://b.com/x", "description": "d3"},
        ]
    }
}


class FakeHttp:
    def __init__(self, payload: object):
        self._payload = payload
        self.get_json_calls = 0

    async def get_json(self, url: str, **kwargs: object) -> object:
        self.get_json_calls += 1
        return self._payload

    async def get_text(self, url: str, request_timeout: float) -> str | None:
        return "<html><body><p>hello content</p></body></html>"


def _service(http: FakeHttp) -> WebSearchService:
    return WebSearchService(
        Settings(
            brave_api_key="k",
            tavily_api_key="",
            exa_api_key="",
            searxng_base_url="",
            search_mode="fallback",
        ),
        http=http,
        cache=MemoryTTLCache(),
    )


async def test_search_dedups_hosts():
    http = FakeHttp(PAYLOAD)
    hits, provider = await _service(http).search("q", max_results=5, fetch_pages=False)
    assert provider == "brave"
    hosts = {hit.href.split("/")[2] for hit in hits}
    assert hosts == {"a.com", "b.com"}


async def test_search_caches_provider_results():
    http = FakeHttp(PAYLOAD)
    service = _service(http)
    await service.search("q", max_results=5, fetch_pages=False)
    await service.search("q", max_results=5, fetch_pages=False)
    assert http.get_json_calls == 1


async def test_fetch_blocks_private_network():
    service = _service(FakeHttp(None))
    page = await service.fetch("http://127.0.0.1/x")
    assert page.status == "blocked"


async def test_fetch_extracts_content():
    service = _service(FakeHttp(None))
    page = await service.fetch("https://example.com/page")
    assert page.status == "ok"
    assert "hello content" in page.text


async def test_empty_query_returns_nothing():
    service = _service(FakeHttp(PAYLOAD))
    hits, provider = await service.search("", max_results=5)
    assert hits == []
    assert provider == ""
