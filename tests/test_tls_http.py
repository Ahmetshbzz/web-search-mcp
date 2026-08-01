import pytest

from web_search_mcp.config import Settings
from web_search_mcp.http import Http


@pytest.mark.asyncio
async def test_http_curl_session():
    settings = Settings(brave_api_key="", tavily_api_key="")
    http = Http(settings)

    assert http.curl_session is not None
    await http.aclose()
    assert http._curl_session is None
