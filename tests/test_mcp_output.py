"""MCP çıktı katmanı: yapısal JSON citation + HTTP transport argümanları."""

import json
import sys

import pytest

from web_search_mcp import mcp as mcp_module
from web_search_mcp.models import SearchHit


class _JsonSvc:
    async def search(self, query: str, **kwargs: object):
        return [
            SearchHit(title="T1", href="https://a.com/1", body="b1", label="a.com"),
            SearchHit(title="T2", href="https://b.com/2", body="b2"),
        ], "brave"


@pytest.mark.asyncio
async def test_web_search_json_response_format(monkeypatch):
    monkeypatch.setattr(mcp_module, "get_service", lambda: _JsonSvc())
    out = await mcp_module.web_search("q", response_format="json")
    data = json.loads(out)

    assert data["query"] == "q"
    assert data["provider"] == "brave"
    assert [r["id"] for r in data["results"]] == ["S1", "S2"]
    assert data["citations"] == [
        {"id": "S1", "title": "T1", "url": "https://a.com/1"},
        {"id": "S2", "title": "T2", "url": "https://b.com/2"},
    ]


def test_main_http_transport_args(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(mcp_module.mcp, "run", lambda **kw: calls.update(kw))
    monkeypatch.setattr(
        sys, "argv", ["web-search-mcp", "--transport", "streamable-http", "--port", "9999"]
    )
    mcp_module.main()
    assert calls == {"transport": "streamable-http", "host": "127.0.0.1", "port": 9999}


def test_main_stdio_default(monkeypatch):
    calls: dict = {}
    monkeypatch.setattr(mcp_module.mcp, "run", lambda **kw: calls.update(kw))
    monkeypatch.setattr(sys, "argv", ["web-search-mcp"])
    mcp_module.main()
    assert calls == {"transport": "stdio"}


@pytest.mark.asyncio
async def test_web_search_media_graceful_failure(monkeypatch):
    class FailSvc:
        async def search_media(self, media_type, query, max_results=8):
            raise RuntimeError("429 Too Many Requests")

    monkeypatch.setattr(mcp_module, "get_service", lambda: FailSvc())
    out = await mcp_module.web_search_media("q", media_type="images")
    assert "Media search failed" in out  # ham traceback sizmiyor
