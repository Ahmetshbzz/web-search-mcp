from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class SearXNGProvider(SearchProvider):
    name = "searxng"

    def available(self) -> bool:
        return bool(self.settings.searxng_base_url.strip())

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        base_url = self.settings.searxng_base_url.rstrip("/")
        url = f"{base_url}/search"
        params = {
            "q": query,
            "format": "json",
            "number_of_results": max_results,
        }
        if recency:
            time_range_map = {"day": "day", "week": "week", "month": "month", "year": "year"}
            if r := time_range_map.get(recency):
                params["time_range"] = r

        # pyrefly: ignore [unexpected-keyword]
        data = await self.http.get_json(url, params=params, timeout=self.settings.search_timeout)
        if not data or not isinstance(data, dict):
            return []

        results: list[ProviderResult] = []
        for item in data.get("results", []):
            if isinstance(item, dict) and item.get("url") and item.get("title"):
                results.append(
                    ProviderResult(
                        href=item["url"],
                        title=item["title"],
                        body=item.get("content", "") or item.get("snippet", ""),
                        published=item.get("publishedDate"),
                    )
                )
        return results[:max_results]
