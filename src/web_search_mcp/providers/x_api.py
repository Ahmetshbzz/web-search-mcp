import os
from urllib.parse import quote

from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class XApiProvider(SearchProvider):
    name = "x_api_v2"

    def available(self) -> bool:
        token = (
            self.settings.x_bearer_token.strip()
            if self.settings
            else os.environ.get("X_BEARER_TOKEN", "").strip()
        )
        return bool(token)

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        token = (
            self.settings.x_bearer_token.strip()
            if self.settings
            else os.environ.get("X_BEARER_TOKEN", "").strip()
        )
        if not token:
            return []

        limit = max(10, min(100, max_results))
        encoded_q = quote(query)
        url = (
            f"https://api.x.com/2/tweets/search/recent?"
            f"query={encoded_q}&max_results={limit}&tweet.fields=created_at,author_id,public_metrics"
        )
        headers = {
            "authorization": f"Bearer {token}",
            "user-agent": "web-search-mcp",
        }
        timeout = getattr(self.settings, "search_timeout", 10.0) if self.settings else 10.0

        data = await self.http.get_json(url, headers=headers, request_timeout=timeout)
        if not data or not isinstance(data, dict):
            return []

        results: list[ProviderResult] = []
        for tweet in data.get("data", []):
            if isinstance(tweet, dict) and tweet.get("id") and tweet.get("text"):
                t_id = tweet["id"]
                text = tweet["text"]
                created = (tweet.get("created_at") or "")[:10]
                metrics = tweet.get("public_metrics", {})
                likes = metrics.get("like_count", 0)
                rts = metrics.get("retweet_count", 0)
                label = f"⭐{likes} 🔁{rts}" if likes or rts else ""

                results.append(
                    ProviderResult(
                        href=f"https://x.com/i/status/{t_id}",
                        title=f"[X API v2 Post] {text[:80]}...",
                        body=f"{text}\nMetrics: {label}",
                        published=created,
                    )
                )
        return results[:max_results]
