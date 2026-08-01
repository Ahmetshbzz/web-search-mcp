"""hybrid_rrf_rerank'in search pipeline'ına bağlanması (relevance sıralama)."""

import pytest

from web_search_mcp.cache import MemoryTTLCache
from web_search_mcp.config import Settings
from web_search_mcp.http import DocumentResult
from web_search_mcp.service import WebSearchService


class RerankHttp:
    """Provider sırası alakasız → içerik sinyali sıralamayı düzeltmeli."""

    PAYLOAD = {
        "web": {
            "results": [
                {"title": "Fluffy cats", "url": "https://a.com/cats", "description": "pets"},
                {"title": "Python GIL", "url": "https://b.com/gil", "description": "python gil"},
            ]
        }
    }

    async def get_json(self, url: str, **kwargs: object) -> object:
        return self.PAYLOAD

    async def get_document(
        self, url: str, request_timeout: float, **kwargs: object
    ) -> DocumentResult:
        pages = {
            "https://a.com/cats": (
                "<html><body><p>cats are fluffy lovely pets "
                "that purr and sleep all day long</p></body></html>"
            ),
            "https://b.com/gil": (
                "<html><body><p>python global interpreter lock gil "
                "enables free threaded concurrency builds</p></body></html>"
            ),
        }
        return DocumentResult(
            content=pages[url], final_url=url, content_type="text/html", status_code=200
        )


@pytest.mark.asyncio
async def test_search_reranks_by_relevance():
    service = WebSearchService(
        Settings(brave_api_key="k", search_mode="fallback"),
        http=RerankHttp(),
        cache=MemoryTTLCache(),
    )
    hits, _ = await service.search("python GIL", max_results=5, fetch_pages=True)
    assert len(hits) == 2
    # Provider sırasında cats önceydi; BM25 rerank python GIL'i öne almalı
    assert hits[0].href == "https://b.com/gil"
