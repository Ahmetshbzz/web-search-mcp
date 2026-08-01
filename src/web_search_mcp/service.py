import asyncio
import time
from collections import OrderedDict
from typing import Literal, NamedTuple

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
    search_fast,
    search_parallel,
    search_with_fallback,
)
from web_search_mcp.ranking import deduplicate_results, rank_results
from web_search_mcp.text import truncate
from web_search_mcp.urls import clean_url, hostname, is_fetchable, matches_domain_filter
from web_search_mcp.vector_rerank import hybrid_rrf_rerank

_logger = get_logger("service")

_PAGE_MEM_MAX = 64  # SQLite önündeki in-memory LRU kapasitesi


class PageContent(NamedTuple):
    """_get_page_content sonucu. kind: ok | empty | too_large | binary"""

    text: str
    date: str
    final_url: str
    kind: str


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
        # In-memory LRU: warm hit'te SQLite + JSON parse maliyeti sıfırlanır
        self._page_mem: OrderedDict[str, tuple[float, tuple[str, str, str]]] = OrderedDict()

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
        max_content_chars: int | None = None,
    ) -> tuple[list[SearchHit], str]:
        query = (query or "").strip()
        if not query:
            return [], ""
        max_results = max(1, min(int(max_results), self.settings.max_provider_results))
        recency = recency if recency in RECENCY_OPTIONS else None
        fetch_top = self.settings.fetch_top_pages if fetch_pages else 0
        search_mode = mode or self.settings.search_mode
        content_limit = max_content_chars or self.settings.max_content_chars

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
        pages: list[PageContent | None] = await asyncio.gather(
            *[
                self._get_page_content(r.href, output_format, self.settings.fetch_timeout)
                if is_fetchable(r.href)
                else asyncio.sleep(0, result=None)
                for r in top
            ],
            return_exceptions=True,
        )

        enriched: list[EnrichedResult] = []
        for result, page in zip(top, pages, strict=False):
            page_text, page_date = "", ""
            if isinstance(page, Exception):
                _logger.debug("page fetch failed for %s", result.href, exc_info=page)
            elif page is not None and page.kind == "ok":
                page_text, page_date = page.text, page.date

            if page_text:
                page_text = chunk_relevant_text(page_text, query, content_limit)

            enriched.append(
                EnrichedResult(
                    title=result.title,
                    href=result.href,
                    snippet=result.body,
                    content=page_text,
                    date=page_date or normalize_date(result.date),
                )
            )

        if recency:
            # Tazelik isteniyorsa tarih öncelikli sırala
            enriched = rank_results(enriched, recency)
        else:
            # Aksi halde BM25 + RRF ile sorgu alakasına göre yeniden sırala
            # (provider sırasına güvenmek yerine içerik sinyali kullanılır)
            enriched = hybrid_rrf_rerank(enriched, query)

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
                    body=truncate(body, content_limit),
                    label=label,
                )
            )
        for result in results[fetch_top:]:
            hits.append(
                SearchHit(
                    title=result.title,
                    href=result.href,
                    body=truncate(result.body, content_limit),
                )
            )
        return hits, provider

    async def search_media(
        self, media_type: str, query: str, max_results: int = 8
    ) -> tuple[list[SearchHit], str]:
        """Brave video/görsel araması (paid plan). Brave yoksa boş döner."""
        query = (query or "").strip()
        if not query:
            return [], ""
        brave = next((p for p in self._providers if p.name == "brave"), None)
        if brave is None or not hasattr(brave, "search_media"):
            return [], ""
        count = max(1, min(int(max_results), self.settings.max_provider_results))
        rows = await brave.search_media(media_type, query, count)  # type: ignore[attr-defined]
        hits = [
            SearchHit(
                title=r.title,
                href=r.href,
                body=truncate(r.body, self.settings.max_content_chars),
                label=r.date,
            )
            for r in rows[:count]
        ]
        return hits, "brave"

    async def fetch(
        self, url: str, output_format: Literal["text", "markdown"] = "text"
    ) -> FetchPage:
        url = clean_url(url.strip())
        # HTTPS upgrade (Lexa parity): http:// verildiyse önce https:// dene
        upgraded = url.startswith("http://")
        if upgraded:
            url = "https://" + url[len("http://") :]
        if not is_fetchable(url):
            return FetchPage(status="blocked")

        page = await self._get_page_content(url, output_format, self.settings.page_timeout)
        if page is None and upgraded:
            # Host HTTPS konuşmuyor olabilir (thinkbroadband vakası) → http'ye düş
            http_url = "http://" + url[len("https://") :]
            page = await self._get_page_content(http_url, output_format, self.settings.page_timeout)
        if page is None:
            return FetchPage(status="unreachable")
        if page.kind != "ok":
            return FetchPage(status=page.kind, final_url=page.final_url)  # type: ignore[arg-type]
        return FetchPage(status="ok", text=page.text, date=page.date, final_url=page.final_url)

    def _mem_get(self, key: str) -> PageContent | None:
        item = self._page_mem.get(key)
        if item is None:
            return None
        expires_at, (text, date, final_url) = item
        if time.time() > expires_at:
            del self._page_mem[key]
            return None
        self._page_mem.move_to_end(key)
        return PageContent(text, date, final_url, "ok")

    def _mem_set(self, key: str, value: tuple[str, str, str]) -> None:
        expires_at = time.time() + self.settings.page_cache_ttl_seconds
        self._page_mem[key] = (expires_at, value)
        self._page_mem.move_to_end(key)
        while len(self._page_mem) > _PAGE_MEM_MAX:
            self._page_mem.popitem(last=False)

    async def _get_page_content(
        self, url: str, output_format: Literal["text", "markdown"], request_timeout: float
    ) -> PageContent | None:
        """Sayfa içeriğini (metin, tarih, final URL, tür) döndürür; sonuçlar cache'lenir.

        None → sayfaya ulaşılamadı. kind="empty" → ulaşıldı ama içerik çıkarılamadı.
        Cache katmanları: in-memory LRU → SQLite → HTTP (streaming, boyut sınırlı).
        """
        is_pdf = url.lower().endswith(".pdf")
        cache_key = f"pdf::{url}" if is_pdf else f"page::{output_format}::{url}"

        mem = self._mem_get(cache_key)
        if mem is not None:
            return mem

        cached = await self.cache.get(cache_key)
        if isinstance(cached, (list, tuple)) and len(cached) >= 2:
            text, date = str(cached[0]), str(cached[1])
            final_url = str(cached[2]) if len(cached) > 2 else ""
            self._mem_set(cache_key, (text, date, final_url))
            return PageContent(text, date, final_url, "ok")

        doc = await self.http.get_document(
            url, request_timeout, max_bytes=self.settings.fetch_max_bytes
        )
        if doc is None or (doc.content is None and not doc.too_large):
            return None
        if doc.too_large:
            return PageContent("", "", doc.final_url, "too_large")

        raw = doc.content
        ct = (doc.content_type or "").lower()
        if isinstance(raw, bytes):
            if is_pdf or "pdf" in ct:
                text, date = extract_pdf(raw), ""
            else:
                return PageContent("", "", doc.final_url, "binary")
        elif "markdown" in ct or ct.startswith("text/plain"):
            # Sunucu zaten markdown/düz metin verdi → extraction atlanır (token + hız)
            text, date = raw.strip(), ""
        else:
            text, date = extract_with_meta(raw, url, output_format=output_format)

        if not text:
            return PageContent("", date, doc.final_url, "empty")

        self._mem_set(cache_key, (text, date, doc.final_url))
        await self.cache.set(
            cache_key, [text, date, doc.final_url], self.settings.page_cache_ttl_seconds
        )
        return PageContent(text, date, doc.final_url, "ok")

    async def _cached_provider_results(
        self, query: str, max_results: int, recency: str | None, search_mode: str
    ) -> tuple[list[ProviderResult], str]:
        # Normalize: "AsyncIO  internals" ile "asyncio internals" aynı cache girişine düşer.
        normalized_query = " ".join(query.casefold().split())
        key = f"search::{normalized_query}|{max_results}|{recency or ''}|{search_mode}"
        cached = await self.cache.get(key)
        if cached is not None and isinstance(cached, (list, tuple)) and len(cached) == 2:
            raw_results, provider = cached
            results = [ProviderResult.model_validate(r) for r in raw_results]
            return results, provider

        p_timeout = self.settings.provider_timeout
        if search_mode == "parallel":
            results, provider = await search_parallel(
                self._providers, query, max_results, recency, p_timeout
            )
        elif search_mode == "fast":
            results, provider = await search_fast(
                self._providers, query, max_results, recency, p_timeout
            )
        else:
            results, provider = await search_with_fallback(
                self._providers, query, max_results, recency, p_timeout
            )

        serializable_results = [r.model_dump() for r in results]
        await self.cache.set(key, (serializable_results, provider), self.settings.cache_ttl_seconds)
        return results, provider
