from unittest.mock import AsyncMock, patch

import pytest

from web_search_mcp.browser_render import BrowserRenderEngine


@pytest.mark.asyncio
async def test_browser_render_engine_mock():
    engine = BrowserRenderEngine()

    mock_page = AsyncMock()
    mock_page.content.return_value = "<html><body><h1>Hello World</h1></body></html>"
    mock_page.evaluate.return_value = "Hello World"

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_playwright
    mock_cm.__aexit__.return_value = None

    with patch("playwright.async_api.async_playwright", return_value=mock_cm):
        res = await engine.render_page("https://example.com")
        assert res["status"] == "ok"
        assert res["rendered_text"] == "Hello World"
