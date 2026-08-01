import pytest

from web_search_mcp.config import Settings
from web_search_mcp.research import DeepResearchEngine
from web_search_mcp.service import WebSearchService


class FakeService(WebSearchService):
    def __init__(self):
        super().__init__(
            Settings(brave_api_key="", tavily_api_key="", exa_api_key="", searxng_base_url="")
        )

    async def search(
        self, query, max_results=3, fetch_pages=True, output_format="markdown", **kwargs
    ):
        from web_search_mcp.models import SearchHit

        return [
            SearchHit(
                title="Deep Test Title",
                href="https://example.com/test",
                body="Sample research body with https://sublink.example.com",
            )
        ], "fake"

    async def fetch(self, url, output_format="markdown"):
        from web_search_mcp.models import FetchPage

        return FetchPage(status="ok", text="Secondary hop content text")


@pytest.mark.asyncio
async def test_deep_research_engine():
    service = FakeService()
    engine = DeepResearchEngine(service)

    res = await engine.execute_research(topic="AsyncIO internals", depth=2, max_pages_per_hop=2)
    assert "# Deep Research Dossier: AsyncIO internals" in res
    assert "Deep Test Title" in res
    assert "https://example.com/test" in res
