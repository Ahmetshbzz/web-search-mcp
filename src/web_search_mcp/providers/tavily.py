from pydantic import BaseModel

from web_search_mcp.config import Settings
from web_search_mcp.dates import normalize_date
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider

_DAYS = {"day": 1, "week": 7, "month": 30, "year": 365}


class _TavilyItem(BaseModel):
    title: str = ""
    url: str = ""
    content: str = ""
    published_date: str = ""


class _TavilyResponse(BaseModel):
    results: list[_TavilyItem] = []


class TavilyProvider(SearchProvider):
    name = "tavily"

    def __init__(self, settings: Settings, http: Http):
        super().__init__(settings, http)
        self._api_key = settings.tavily_api_key

    def available(self) -> bool:
        return bool(self._api_key)

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        body: dict[str, object] = {
            "api_key": self._api_key,
            "query": query,
            "max_results": min(max_results, self.settings.max_provider_results),
            "search_depth": "advanced",
        }
        days = _DAYS.get(recency or "")
        if days:
            body["topic"] = "news"
            body["days"] = days
        data = await self.http.get_json(
            "https://api.tavily.com/search",
            headers={"Content-Type": "application/json"},
            request_timeout=self.settings.search_timeout,
            json_body=body,
        )
        response = _TavilyResponse.model_validate(data)
        out: list[ProviderResult] = []
        for item in response.results:
            out.append(
                ProviderResult(
                    title=item.title,
                    href=item.url,
                    body=item.content,
                    date=normalize_date(item.published_date),
                )
            )
        return out
