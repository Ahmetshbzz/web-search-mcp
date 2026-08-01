import pytest

from web_search_mcp.browser_render import BrowserRenderEngine


@pytest.mark.asyncio
async def test_browser_render_engine_basic():
    engine = BrowserRenderEngine()
    result = await engine.render_page("https://httpbin.org/get", wait_until="domcontentloaded")
    assert result["status"] == "ok"
    assert "httpbin" in result["rendered_text"].lower() or "httpbin" in result["url"]
