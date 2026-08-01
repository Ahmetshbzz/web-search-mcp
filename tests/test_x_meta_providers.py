import pytest

from web_search_mcp.providers.meta_dev import MetaDevProvider
from web_search_mcp.providers.x_dev import XDevProvider
from web_search_mcp.site_discovery import SiteDiscoveryEngine


class FakeXMetaHttp:
    async def get_text(self, url: str, **kwargs) -> str:
        if "llms-full.txt" in url:
            return "# Full Documentation Context\nAll X API endpoints markdown context."
        if "llms.txt" in url:
            return "# X API llms.txt Index\n- [Posts API](https://docs.x.com/x-api/llms.txt)"
        if "robots.txt" in url:
            return "User-agent: *\nAllow: /"
        if "sitemap.xml" in url:
            return "<xml></xml>"
        if "duckduckgo.com" in url or "docs.x.com" in url or "facebook.com" in url:
            return (
                '<div class="result">'
                '<h2 class="result__title"><a href="https://docs.x.com/x-api/posts/get.md">'
                "GET /2/tweets/:id</a></h2>"
                '<div class="result__snippet">Returns information about a single Tweet.</div>'
                "</div>"
            )
        return ""


@pytest.mark.asyncio
async def test_x_dev_provider_mock():
    http = FakeXMetaHttp()
    provider = XDevProvider(settings=None, http=http)
    results = await provider.search("get tweet by id", max_results=2, recency=None)
    assert len(results) == 1
    assert "GET /2/tweets/:id" in results[0].title
    assert "docs.x.com" in results[0].href


@pytest.mark.asyncio
async def test_meta_dev_provider_mock():
    http = FakeXMetaHttp()
    provider = MetaDevProvider(settings=None, http=http)
    results = await provider.search("whatsapp Business API", max_results=2, recency=None)
    assert len(results) == 1
    assert "developers.facebook.com" in results[0].href or "docs.x.com" in results[0].href


@pytest.mark.asyncio
async def test_site_discovery_x_llms_full():
    http = FakeXMetaHttp()
    engine = SiteDiscoveryEngine(http=http)
    data = await engine.discover("docs.x.com")
    assert data["has_llms_full_txt"] is True
    assert "Full Documentation Context" in data["llms_full_preview"]
