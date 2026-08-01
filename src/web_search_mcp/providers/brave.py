import asyncio
import re

from pydantic import BaseModel

from web_search_mcp.config import Settings
from web_search_mcp.dates import normalize_date
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider

_FRESHNESS = {"day": "pd", "week": "pw", "month": "pm", "year": "py"}

# Bu recency'lerde web + news endpoint'leri paralel sorgulanır (taze haber kalitesi)
_NEWS_RECENCY = {"day", "week"}


class _BraveItem(BaseModel):
    title: str = ""
    url: str = ""
    description: str = ""
    page_age: str = ""
    age: str = ""


class _BraveWeb(BaseModel):
    results: list[_BraveItem] = []


class _BraveWebResponse(BaseModel):
    web: _BraveWeb = _BraveWeb()


class _BraveNewsResponse(BaseModel):
    results: list[_BraveItem] = []


class _BraveVideoItem(BaseModel):
    title: str = ""
    url: str = ""
    description: str = ""
    age: str = ""
    page_age: str = ""
    duration: str = ""


class _BraveVideosResponse(BaseModel):
    results: list[_BraveVideoItem] = []


class _BraveImageProperties(BaseModel):
    url: str = ""
    width: int = 0
    height: int = 0


class _BraveImageItem(BaseModel):
    title: str = ""
    url: str = ""
    source: str = ""
    page_age: str = ""
    properties: _BraveImageProperties = _BraveImageProperties()


class _BraveImagesResponse(BaseModel):
    results: list[_BraveImageItem] = []


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
        count = min(max_results, self.settings.max_provider_results)
        if recency in _NEWS_RECENCY:
            # Tazelik kritikse news endpoint'i de paralel ateşlenir; haber
            # sonuçları öne alınır. Biri patlarsa diğeri tek başına yeter.
            news_res, web_res = await asyncio.gather(
                self._search_news(query, count, recency),
                self._search_web(query, count, recency),
                return_exceptions=True,
            )
            news_rows = news_res if isinstance(news_res, list) else []
            web_rows = web_res if isinstance(web_res, list) else []
            if not news_rows and not web_rows and isinstance(web_res, Exception):
                raise web_res
            return news_rows + web_rows
        return await self._search_web(query, count, recency)

    async def _search_web(
        self, query: str, count: int, recency: str | None
    ) -> list[ProviderResult]:
        params: dict[str, object] = {"q": query, "count": count}
        freshness = _FRESHNESS.get(recency or "")
        if freshness:
            params["freshness"] = freshness
        data = await self.http.get_json(
            "https://api.search.brave.com/res/v1/web/search",
            params=params,
            headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
            request_timeout=self.settings.search_timeout,
        )
        response = _BraveWebResponse.model_validate(data)
        return [self._to_result(item) for item in response.web.results]

    async def _search_news(
        self, query: str, count: int, recency: str | None
    ) -> list[ProviderResult]:
        params: dict[str, object] = {"q": query, "count": count}
        freshness = _FRESHNESS.get(recency or "")
        if freshness:
            params["freshness"] = freshness
        data = await self.http.get_json(
            "https://api.search.brave.com/res/v1/news/search",
            params=params,
            headers={"X-Subscription-Token": self._api_key, "Accept": "application/json"},
            request_timeout=self.settings.search_timeout,
        )
        response = _BraveNewsResponse.model_validate(data)
        return [self._to_result(item) for item in response.results]

    async def search_media(self, media_type: str, query: str, count: int) -> list[ProviderResult]:
        """Brave video/görsel endpoint'leri (paid plan). body alanında:
        videos → açıklama, images → direkt görsel URL'i; date alanında meta."""
        params: dict[str, object] = {"q": query, "count": count}
        headers = {"X-Subscription-Token": self._api_key, "Accept": "application/json"}
        if media_type == "videos":
            data = await self.http.get_json(
                "https://api.search.brave.com/res/v1/videos/search",
                params=params,
                headers=headers,
                request_timeout=self.settings.search_timeout,
            )
            response = _BraveVideosResponse.model_validate(data)
            return [
                ProviderResult(
                    title=i.title,
                    href=i.url,
                    body=re.sub(r"<[^>]+>", "", i.description),
                    date=i.duration or normalize_date(i.page_age or i.age),
                )
                for i in response.results
            ]
        if media_type == "images":
            data = await self.http.get_json(
                "https://api.search.brave.com/res/v1/images/search",
                params=params,
                headers=headers,
                request_timeout=self.settings.search_timeout,
            )
            response = _BraveImagesResponse.model_validate(data)
            out: list[ProviderResult] = []
            for i in response.results:
                dims = f"{i.properties.width}x{i.properties.height}" if i.properties.width else ""
                out.append(
                    ProviderResult(
                        title=i.title or i.source,
                        href=i.url,
                        body=i.properties.url,  # direkt görsel URL'i
                        date=dims or normalize_date(i.page_age),
                    )
                )
            return out
        raise ValueError(f"unknown media type: {media_type}")

    @staticmethod
    def _to_result(item: _BraveItem) -> ProviderResult:
        return ProviderResult(
            title=item.title,
            href=item.url,
            body=re.sub(r"<[^>]+>", "", item.description),
            date=normalize_date(item.page_age or item.age),
        )
