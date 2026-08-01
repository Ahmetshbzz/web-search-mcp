import pytest

from web_search_mcp.config import Settings
from web_search_mcp.models import FetchPage
from web_search_mcp.service import WebSearchService
from web_search_mcp.structured import StructuredExtractor


class FakeFetchService(WebSearchService):
    def __init__(self):
        super().__init__(
            Settings(brave_api_key="", tavily_api_key="", exa_api_key="", searxng_base_url="")
        )

    async def fetch(self, url, output_format="text"):
        return FetchPage(
            status="ok",
            text="Product: Super Widget 3000\nPrice: $299\nVersion: v2.5",
            date="2026-05-01",
        )


@pytest.mark.asyncio
async def test_structured_extractor():
    service = FakeFetchService()
    extractor = StructuredExtractor(service)

    schema = '{"Product": "str", "Price": "str"}'
    data = await extractor.extract_structured_data("https://example.com/item", schema)

    assert data["source_url"] == "https://example.com/item"
    assert data["extracted_data"]["Product"] == "Super Widget 3000"
    assert data["extracted_data"]["Price"] == "$299"
