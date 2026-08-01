from web_search_mcp.config import Settings
from web_search_mcp.models import ProviderResult
from web_search_mcp.providers import (
    build_fallback_chain,
    search_with_fallback,
)
from web_search_mcp.providers.brave import BraveProvider
from web_search_mcp.providers.tavily import TavilyProvider

BRAVE_PAYLOAD = {
    "web": {
        "results": [
            {
                "title": "T",
                "url": "https://example.com",
                "description": "<b>d</b>",
                "age": "2 days ago",
            }
        ]
    }
}

TAVILY_PAYLOAD = {
    "results": [
        {"title": "T", "url": "https://example.com", "content": "c", "published_date": "2024-05-01"}
    ]
}


class FakeHttp:
    def __init__(self, payload: object):
        self._payload = payload
        self.get_json_calls = 0

    async def get_json(self, url: str, **kwargs: object) -> object:
        self.get_json_calls += 1
        return self._payload

    async def get_text(self, url: str, request_timeout: float) -> str | None:
        return None


async def test_brave_normalizes():
    provider = BraveProvider(Settings(brave_api_key="k"), FakeHttp(BRAVE_PAYLOAD))
    rows = await provider.search("q", 5, None)
    assert rows[0].href == "https://example.com"
    assert rows[0].body == "d"
    assert rows[0].date  # "2 days ago" parsed to a real date


async def test_tavily_normalizes():
    provider = TavilyProvider(Settings(tavily_api_key="k"), FakeHttp(TAVILY_PAYLOAD))
    rows = await provider.search("q", 5, None)
    assert rows[0].body == "c"
    assert rows[0].date == "2024-05-01"


def test_chain_ddg_only_without_keys():
    chain = build_fallback_chain(
        Settings(
            brave_api_key="",
            tavily_api_key="",
            exa_api_key="",
            x_bearer_token="",
            searxng_base_url="",
        ),
        FakeHttp(None),
    )
    assert [p.name for p in chain] == ["arxiv", "github", "x_osint", "meta_osint", "ddg"]


def test_chain_priority_with_keys():
    chain = build_fallback_chain(
        Settings(
            brave_api_key="k",
            tavily_api_key="k2",
            exa_api_key="k3",
            x_bearer_token="x_token",
            searxng_base_url="https://searx.example.com",
        ),
        FakeHttp(None),
    )
    assert [p.name for p in chain] == [
        "brave",
        "tavily",
        "exa",
        "x_api_v2",
        "arxiv",
        "github",
        "x_osint",
        "meta_osint",
        "searxng",
        "ddg",
    ]


class FailProvider:
    name = "fail"

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        raise RuntimeError("boom")


class OkProvider:
    name = "ok"

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        return [ProviderResult(title="x", href="https://x.com")]


async def test_fallback_tries_next_provider():
    results, provider = await search_with_fallback([FailProvider(), OkProvider()], "q", 5, None)
    assert provider == "ok"
    assert len(results) == 1


async def test_fallback_returns_empty_when_all_fail():
    results, provider = await search_with_fallback([FailProvider()], "q", 5, None)
    assert results == []
    assert provider == ""


class _BraveRoutingHttp:
    """news/web endpoint'lerini ayırt eden fake."""

    def __init__(self, fail_news: bool = False):
        self.urls: list[str] = []
        self.fail_news = fail_news

    async def get_json(self, url: str, **kwargs: object) -> object:
        self.urls.append(url)
        if "news/search" in url:
            if self.fail_news:
                raise RuntimeError("news endpoint not subscribed")
            return {
                "results": [
                    {
                        "title": "Breaking News",
                        "url": "https://news.com/1",
                        "description": "fresh",
                        "age": "2 hours ago",
                    }
                ]
            }
        return {
            "web": {
                "results": [{"title": "Web Result", "url": "https://web.com/1", "description": "d"}]
            }
        }


async def test_brave_recency_fires_news_and_web():
    http = _BraveRoutingHttp()
    provider = BraveProvider(Settings(brave_api_key="k"), http)  # type: ignore[arg-type]
    rows = await provider.search("q", max_results=5, recency="day")

    kinds = {"news" if "news/search" in u else "web" for u in http.urls}
    assert kinds == {"news", "web"}
    assert rows[0].title == "Breaking News"  # haber önce gelir
    assert rows[0].date != ""  # '2 hours ago' normalize edildi
    assert any(r.title == "Web Result" for r in rows)


async def test_brave_no_recency_web_only():
    http = _BraveRoutingHttp()
    provider = BraveProvider(Settings(brave_api_key="k"), http)  # type: ignore[arg-type]
    rows = await provider.search("q", max_results=5, recency=None)

    assert all("news/search" not in u for u in http.urls)
    assert [r.title for r in rows] == ["Web Result"]


async def test_brave_news_failure_falls_back_to_web():
    http = _BraveRoutingHttp(fail_news=True)
    provider = BraveProvider(Settings(brave_api_key="k"), http)  # type: ignore[arg-type]
    rows = await provider.search("q", max_results=5, recency="day")

    assert [r.title for r in rows] == ["Web Result"]
