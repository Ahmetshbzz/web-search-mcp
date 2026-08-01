import asyncio
from typing import Literal

from web_search_mcp.cache import SQLiteTTLCache, TTLCache
from web_search_mcp.config import RECENCY_OPTIONS, Settings, get_settings
from web_search_mcp.dates import normalize_date
from web_search_mcp.extractors import (
    chunk_relevant_text,
    extract_pdf,
    extract_with_meta,
)
from web_search_mcp.http import Http
from web_search_mcp.models import EnrichedResult, FetchPage, ProviderResult, SearchHit
from web_search_mcp.observability import get_logger
from web_search_mcp.providers import (
    build_fallback_chain,
    search_parallel,
    search_with_fallback,
)
from web_search_mcp.ranking import deduplicate_results, rank_results
from web_search_mcp.text import truncate
from web_search_mcp.urls import clean_url, hostname, is_fetchable, matches_domain_filter

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
        self.cache = cache or SQLiteTTLCache(self.settings.cache_db_path)
        self._providers = build_fallback_chain(self.settings, self.http)

    async def search(
        self,
        query: str,
        max_results: int = 8,
        recency: str | None = None,
        fetch_pages: bool = True,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        mode: str | None = None,
        output_format: Literal["text", "markdown"] = "text",
    ) -> tuple[list[SearchHit], str]:
        query = (query or "").strip()
        if not query:
            return [], ""
        max_results = max(1, min(int(max_results), self.settings.max_provider_results))
        recency = recency if recency in RECENCY_OPTIONS else None
        fetch_top = self.settings.fetch_top_pages if fetch_pages else 0
        search_mode = mode or self.settings.search_mode

        results, provider = await self._cached_provider_results(
            query, max_results, recency, search_mode
        )
        if not results:
            return [], ""

        # Filter by domain
        results = [
            r for r in results if matches_domain_filter(r.href, include_domains, exclude_domains)
        ]
        if not results:
            return [], provider

        results = deduplicate_results(results)

        top = results[:fetch_top]
        pages: list[str | bytes | None] = [None] * len(top)
        try:
            pages = await asyncio.gather(
                *[
                    self._fetch_raw_content(r.href)
                    if is_fetchable(r.href)
                    else asyncio.sleep(0, result=None)
                    for r in top
                ]
            )
        except Exception:
            _logger.debug("page fetch failed", exc_info=True)

        enriched: list[EnrichedResult] = []
        for result, content_raw in zip(top, pages, strict=False):
            page_text, page_date = "", ""
            if isinstance(content_raw, bytes):
                page_text = extract_pdf(content_raw)
            elif isinstance(content_raw, str) and content_raw:
                page_text, page_date = extract_with_meta(
                    content_raw, result.href, output_format=output_format
                )

            if page_text:
                page_text = chunk_relevant_text(page_text, query, self.settings.max_content_chars)

            enriched.append(
                EnrichedResult(
                    title=result.title,
                    href=result.href,
                    snippet=result.body,
                    content=page_text,
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

    async def fetch(
        self, url: str, output_format: Literal["text", "markdown"] = "text"
    ) -> FetchPage:
        url = clean_url(url.strip())
        if not is_fetchable(url):
            return FetchPage(status="blocked")

        if url.lower().endswith(".pdf"):
            pdf_bytes = await self.http.get_bytes(url, self.settings.page_timeout)
            if not pdf_bytes:
                return FetchPage(status="unreachable")
            pdf_text = extract_pdf(pdf_bytes)
            if not pdf_text:
                return FetchPage(status="empty")
            return FetchPage(status="ok", text=pdf_text)

        html = await self.http.get_text(url, self.settings.page_timeout)
        if not html:
            return FetchPage(status="unreachable")
        text, date = extract_with_meta(html, url, output_format=output_format)
        if not text:
            return FetchPage(status="empty")
        return FetchPage(status="ok", text=text, date=date)

    async def _fetch_raw_content(self, url: str) -> str | bytes | None:
        if url.lower().endswith(".pdf"):
            return await self.http.get_bytes(url, self.settings.fetch_timeout)
        return await self.http.get_text(url, self.settings.fetch_timeout)

    async def _cached_provider_results(
        self, query: str, max_results: int, recency: str | None, search_mode: str
    ) -> tuple[list[ProviderResult], str]:
        key = f"{query}|{max_results}|{recency or ''}|{search_mode}"
        cached = await self.cache.get(key)
        if cached is not None and isinstance(cached, (list, tuple)) and len(cached) == 2:
            raw_results, provider = cached
            results = [ProviderResult.model_validate(r) for r in raw_results]
            return results, provider

        if search_mode == "parallel":
            results, provider = await search_parallel(self._providers, query, max_results, recency)
        else:
            results, provider = await search_with_fallback(
                self._providers, query, max_results, recency
            )

        serializable_results = [r.model_dump() for r in results]
        await self.cache.set(key, (serializable_results, provider), self.settings.cache_ttl_seconds)
        return results, provider
