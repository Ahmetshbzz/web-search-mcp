"""Deep research reformulation hop testleri."""

import pytest

from web_search_mcp.config import Settings
from web_search_mcp.models import FetchPage, SearchHit
from web_search_mcp.research import DeepResearchEngine
from web_search_mcp.service import WebSearchService


def test_refine_queries_extracts_salient_terms():
    hits = [
        SearchHit(
            title="Python GIL removal in PEP 703",
            href="https://a.com/1",
            body="free-threaded builds enable parallelism without the interpreter lock",
        ),
        SearchHit(
            title="Free-threaded CPython guide",
            href="https://b.com/2",
            body="nogil free-threaded python builds and parallelism benchmarks",
        ),
    ]
    queries = DeepResearchEngine._refine_queries("python GIL", hits)
    assert queries
    assert all(q.startswith("python GIL ") for q in queries)
    flat = " ".join(queries)
    assert "free-threaded" in flat or "parallelism" in flat


class _RefineCountingService(WebSearchService):
    def __init__(self):
        super().__init__(
            Settings(brave_api_key="", tavily_api_key="", exa_api_key="", searxng_base_url="")
        )
        self.queries_seen: list[str] = []

    async def search(self, query, **kwargs):
        self.queries_seen.append(query)
        return [
            SearchHit(
                title=f"{query} deep dive nogil threading",
                href=f"https://example.com/{len(self.queries_seen)}",
                body="nogil threading builds parallelism interpreter lock free-threaded",
            )
        ], "fake"

    async def fetch(self, url, output_format="markdown"):
        return FetchPage(status="ok", text="hop2")


@pytest.mark.asyncio
async def test_research_reformulation_hop_fires():
    service = _RefineCountingService()
    engine = DeepResearchEngine(service)
    await engine.execute_research(topic="python GIL", depth=2, max_pages_per_hop=2)

    # 3 birincil + en az 1 reformüle sorgu (terim yeterliyse 2)
    assert len(service.queries_seen) >= 4
    refined = service.queries_seen[3:]
    assert all(q.startswith("python GIL ") for q in refined)
