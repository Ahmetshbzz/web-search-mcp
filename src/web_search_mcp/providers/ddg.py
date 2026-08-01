import asyncio

from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider

_TIMELIMIT = {"day": "d", "week": "w", "month": "m", "year": "y"}


class DdgProvider(SearchProvider):
    name = "ddg"

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        # ddgs senkron; asyncio.to_thread içinde çağrılır. region="wt-wt": BÖLGESİZ arama.
        from ddgs import DDGS

        timelimit = _TIMELIMIT.get(recency or "")
        raw = await asyncio.to_thread(
            DDGS().text, query, region="wt-wt", timelimit=timelimit, max_results=max_results
        )
        return [
            ProviderResult(
                title=str(r.get("title", "")),
                href=str(r.get("href", "")),
                body=str(r.get("body", "")),
            )
            for r in raw
        ]
