import re

from pydantic import BaseModel

from web_search_mcp.config import Settings
from web_search_mcp.dates import normalize_date
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider

_FRESHNESS = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}


class _BraveItem(BaseModel):
    title: str = ""
    url: str = ""
    description: str = ""
    page_age: str = ""
    age: str = ""


class _BraveWeb(BaseModel):
    results: list[_BraveItem] = []


class _BraveResponse(BaseModel):
    web: _BraveWeb = _BraveWeb()


class BraveProvider(SearchProvider):
    name = "brave"

    def __init__(self, settings: Settings, http: Http):
        super().__init__(settings, http)
        self._api_key = settings.brave_api_key

    def available(self) -> bool:
        return bool(self._api_key)

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        params: dict[str, object] = {
            "q": query,
            "count": min(max_results, self.settings.max_provider_results),
        }
        freshness = _FRESHNESS.get(recency or "")
        if freshness:
            params["freshness"] = freshness
        data = await self.http.get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params=params,
            headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
            request_timeout=self.settings.search_timeout,
        )
        response = _BraveResponse.model_validate(data)
        out: list[ProviderResult] = []
        for item in response.web.results:
            out.append(
                ProviderResult(
                    title=item.title,
                    href=item.url,
                    body=re.sub(r"<[^>]+>", "", item.description),
                    date=normalize_date(item.page_age or item.age),
                )
            )
        return out
