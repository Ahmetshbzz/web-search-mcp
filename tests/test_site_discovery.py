import pytest

from web_search_mcp.config import Settings
from web_search_mcp.http import Http
from web_search_mcp.site_discovery import SiteDiscoveryEngine


class FakeDiscoveryHttp(Http):
    def __init__(self):
        super().__init__(Settings(brave_api_key="", tavily_api_key=""))

    async def get_text(self, url: str, request_timeout: float) -> str | None:
        if "robots.txt" in url:
            return "User-agent: *\nDisallow: /admin\nSitemap: https://example.com/sitemap.xml"
        if "llms.txt" in url:
            return "# Site Docs for LLMs\n> Documentation index"
        if "sitemap.xml" in url:
            return "<xml><url><loc>https://example.com/page1</loc></url></xml>"
        return None


@pytest.mark.asyncio
async def test_site_discovery_engine():
    http = FakeDiscoveryHttp()
    engine = SiteDiscoveryEngine(http)

    res = await engine.discover("example.com")
    assert res["target_site"] == "https://example.com"
    assert res["has_robots_txt"] is True
    assert res["has_llms_txt"] is True
    assert res["has_sitemap_xml"] is True
    assert "https://example.com/sitemap.xml" in res["sitemaps_found"]
