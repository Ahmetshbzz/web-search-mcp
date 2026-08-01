import pytest

from web_search_mcp.providers.meta_osint import MetaOsintProvider
from web_search_mcp.providers.x_osint import XOsintProvider
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
        if "facebook.com" in url or "instagram.com" in url:
            return (
                '<div class="result">'
                '<h2 class="result__title"><a href="https://facebook.com/page/posts/123">'
                "Facebook Post</a></h2>"
                '<div class="result__snippet">Public Facebook post snippet.</div>'
                "</div>"
            )
        if "duckduckgo.com" in url or "x.com" in url:
            return (
                '<div class="result">'
                '<h2 class="result__title"><a href="https://x.com/user/status/123456">'
                "Live Tweet by @user</a></h2>"
                '<div class="result__snippet">Sample live tweet content about AI agents.</div>'
                "</div>"
            )
        return ""


@pytest.mark.asyncio
async def test_x_osint_provider_mock():
    http = FakeXMetaHttp()
    provider = XOsintProvider(settings=None, http=http)
    results = await provider.search("AI agents", max_results=2, recency=None)
    assert len(results) == 1
    assert "Live Tweet" in results[0].title
    assert "x.com" in results[0].href


@pytest.mark.asyncio
async def test_meta_osint_provider_mock():
    http = FakeXMetaHttp()
    provider = MetaOsintProvider(settings=None, http=http)
    results = await provider.search("tech news", max_results=2, recency=None)
    assert len(results) == 1
    assert "Facebook" in results[0].title or "facebook.com" in results[0].href


@pytest.mark.asyncio
async def test_site_discovery_x_llms_full():
    http = FakeXMetaHttp()
    engine = SiteDiscoveryEngine(http=http)
    data = await engine.discover("docs.x.com")
    assert data["has_llms_full_txt"] is True
    assert "Full Documentation Context" in data["llms_full_preview"]
