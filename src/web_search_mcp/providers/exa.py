from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class ExaProvider(SearchProvider):
    name = "exa"

    def available(self) -> bool:
        return bool(self.settings.exa_api_key.strip())

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        url = "https://api.exa.ai/search"
        headers = {
            "x-api-key": self.settings.exa_api_key,
            "content-type": "application/json",
        }
        payload = {
            "query": query,
            "numResults": max_results,
            "type": "auto",
        }
        data = await self.http.post_json(
            url, headers=headers, json_data=payload, request_timeout=self.settings.search_timeout
        )
        if not data or not isinstance(data, dict):
            return []

        results: list[ProviderResult] = []
        for item in data.get("results", []):
            if isinstance(item, dict) and item.get("url") and item.get("title"):
                results.append(
                    ProviderResult(
                        href=item["url"],
                        title=item["title"],
                        body=item.get("snippet", "") or item.get("text", "") or "",
                        published=item.get("publishedDate"),
                    )
                )
        return results[:max_results]
