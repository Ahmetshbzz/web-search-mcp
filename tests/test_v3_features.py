import pytest

from web_search_mcp.ocr import extract_text_from_image_bytes
from web_search_mcp.providers.arxiv import ArxivProvider
from web_search_mcp.providers.github import GithubProvider
from web_search_mcp.proxy import ProxyManager


def test_proxy_manager_configured():
    assert isinstance(ProxyManager.is_proxy_configured(), bool)


def test_ocr_empty_bytes():
    assert extract_text_from_image_bytes(b"") == ""


@pytest.mark.asyncio
async def test_arxiv_provider_mock(monkeypatch):
    class FakeHttp:
        async def get_text(self, url: str, **kwargs) -> str:
            return """<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom">
              <entry>
                <title>Deep Learning Paper</title>
                <summary>Abstract summary of paper</summary>
                <id>http://arxiv.org/abs/2401.00001</id>
                <published>2026-01-01T00:00:00Z</published>
              </entry>
            </feed>"""

    provider = ArxivProvider(settings=None, http=FakeHttp())
    results = await provider.search("deep learning", max_results=2, recency=None)
    assert len(results) == 1
    assert "Deep Learning Paper" in results[0].title
    assert results[0].href == "http://arxiv.org/abs/2401.00001"


@pytest.mark.asyncio
async def test_github_provider_mock(monkeypatch):
    class FakeHttp:
        async def get_json(self, url: str, **kwargs) -> dict:
            return {
                "items": [
                    {
                        "full_name": "owner/repo",
                        "html_url": "https://github.com/owner/repo",
                        "stargazers_count": 100,
                        "language": "Python",
                        "description": "Cool repo",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ]
            }

    provider = GithubProvider(settings=None, http=FakeHttp())
    results = await provider.search("python repo", max_results=2, recency=None)
    assert len(results) == 1
    assert "owner/repo" in results[0].title
    assert results[0].href == "https://github.com/owner/repo"
