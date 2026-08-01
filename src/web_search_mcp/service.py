import asyncio

from web_search_mcp.cache import MemoryTTLCache, TTLCache
from web_search_mcp.config import RECENCY_OPTIONS, Settings, get_settings
from web_search_mcp.dates import normalize_date
from web_search_mcp.extractors import extract_with_meta
from web_search_mcp.http import Http
from web_search_mcp.models import EnrichedResult, FetchPage, ProviderResult, SearchHit
from web_search_mcp.observability import get_logger
from web_search_mcp.providers import build_fallback_chain, search_with_fallback
from web_search_mcp.ranking import rank_results
from web_search_mcp.text import truncate
from web_search_mcp.urls import clean_url, hostname, is_fetchable

_logger = get_logger("service")


class WebSearchService:
    def __init__(
        self,
        settings: Settings | None = None,
        http: Http | None = None,
        cache: TTLCache | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http = http or Http(self.settings)
        self.cache = cache or MemoryTTLCache()
        self._providers = build_fallback_chain(self.settings, self.http)

    async def search(
        self,
        query: str,
        max_results: int = 8,
        recency: str | None = None,
        fetch_pages: bool = True,
    ) -> tuple[list[SearchHit], str]:
        query = (query or "").strip()
        if not query:
            return [], ""
        max_results = max(1, min(int(max_results), self.settings.max_provider_results))
        recency = recency if recency in RECENCY_OPTIONS else None
        fetch_top = self.settings.fetch_top_pages if fetch_pages else 0

        results, provider = await self._cached_provider_results(query, max_results, recency)
        if not results:
            return [], ""

        results = self._dedupe(results)

        top = results[:fetch_top]
        pages: list[str | None] = [None] * len(top)
        try:
            pages = await asyncio.gather(
                *[
                    self.http.get_text(r.href, self.settings.fetch_timeout)
                    if is_fetchable(r.href)
                    else asyncio.sleep(0, result=None)
                    for r in top
                ]
            )
        except Exception:  # noqa: BLE001 — çekim hatasında snippet'e düş.
            _logger.debug("page fetch failed", exc_info=True)

        enriched: list[EnrichedResult] = []
        for result, html in zip(top, pages, strict=False):
            content, page_date = extract_with_meta(html, result.href) if html else ("", "")
            enriched.append(
                EnrichedResult(
                    title=result.title,
                    href=result.href,
                    snippet=result.body,
                    content=content,
                    date=page_date or normalize_date(result.date),
                )
            )

        enriched = rank_results(enriched, recency)

        hits: list[SearchHit] = []
        for item in enriched:
            host = hostname(item.href)
            label = (
                f"{host} · {item.date}"
                if item.date
                else f"{host} · yayın tarihi yok (güncellik için tek başına güvenme)"
            )
            body = item.content or item.snippet
            hits.append(
                SearchHit(
                    title=item.title,
                    href=item.href,
                    body=truncate(body, self.settings.max_content_chars),
                    label=label,
                )
            )
        for result in results[fetch_top:]:
            hits.append(
                SearchHit(
                    title=result.title,
                    href=result.href,
                    body=truncate(result.body, self.settings.max_content_chars),
                )
            )
        return hits, provider

    async def fetch(self, url: str) -> FetchPage:
        url = clean_url(url.strip())
        if not is_fetchable(url):
            return FetchPage(status="blocked")
        html = await self.http.get_text(url, self.settings.page_timeout)
        if not html:
            return FetchPage(status="unreachable")
        text, date = extract_with_meta(html, url)
        if not text:
            return FetchPage(status="empty")
        return FetchPage(status="ok", text=text, date=date)

    async def _cached_provider_results(
        self, query: str, max_results: int, recency: str | None
    ) -> tuple[list[ProviderResult], str]:
        key = f"{query}|{max_results}|{recency or ''}"
        cached = self.cache.get(key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        results, provider = await search_with_fallback(
            self._providers, query, max_results, recency
        )
        self.cache.set(key, (results, provider), self.settings.cache_ttl_seconds)
        return results, provider

    @staticmethod
    def _dedupe(results: list[ProviderResult]) -> list[ProviderResult]:
        """Host + URL dedup: aynı domainden/sayfadan birden çok sonuç → kaynak çeşitliliği."""
        seen_hosts: set[str] = set()
        seen_urls: set[str] = set()
        deduped: list[ProviderResult] = []
        for result in results:
            href = clean_url(result.href)
            host = hostname(href)
            if host and host not in seen_hosts and href not in seen_urls:
                seen_hosts.add(host)
                seen_urls.add(href)
                deduped.append(result.model_copy(update={"href": href}))
        return deduped or results
