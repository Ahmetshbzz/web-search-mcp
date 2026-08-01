import os
from urllib.parse import quote

from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class GithubProvider(SearchProvider):
    name = "github"

    def available(self) -> bool:
        return True

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        encoded = quote(query)
        url = f"https://api.github.com/search/repositories?q={encoded}&per_page={max_results}"
        headers = {
            "accept": "application/vnd.github+json",
            "user-agent": "web-search-mcp",
        }
        github_token = os.environ.get("GITHUB_TOKEN", "").strip()
        if github_token:
            headers["authorization"] = f"Bearer {github_token}"

        timeout = getattr(self.settings, "search_timeout", 10.0) if self.settings else 10.0
        data = await self.http.get_json(url, headers=headers, request_timeout=timeout)
        if not data or not isinstance(data, dict):
            return []

        results: list[ProviderResult] = []
        for item in data.get("items", []):
            if isinstance(item, dict) and item.get("html_url") and item.get("full_name"):
                stars = item.get("stargazers_count", 0)
                lang = item.get("language") or "Code"
                desc = item.get("description") or ""
                results.append(
                    ProviderResult(
                        href=item["html_url"],
                        title=f"[GitHub Repo] {item['full_name']} ({lang} ⭐{stars})",
                        body=desc,
                        published=(item.get("updated_at") or "")[:10],
                    )
                )
        return results[:max_results]
