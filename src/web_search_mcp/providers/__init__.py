import asyncio

from web_search_mcp.circuit_breaker import CircuitBreaker
from web_search_mcp.config import Settings
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult
from web_search_mcp.observability import get_logger
from web_search_mcp.providers.arxiv import ArxivProvider
from web_search_mcp.providers.base import SearchProvider
from web_search_mcp.providers.brave import BraveProvider
from web_search_mcp.providers.ddg import DdgProvider
from web_search_mcp.providers.exa import ExaProvider
from web_search_mcp.providers.github import GithubProvider
from web_search_mcp.providers.meta_osint import MetaOsintProvider
from web_search_mcp.providers.searxng import SearXNGProvider
from web_search_mcp.providers.tavily import TavilyProvider
from web_search_mcp.providers.x_api import XApiProvider
from web_search_mcp.providers.x_osint import XOsintProvider

_logger = get_logger("providers")
_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(provider_name: str) -> CircuitBreaker:
    if provider_name not in _breakers:
        _breakers[provider_name] = CircuitBreaker(name=provider_name)
    return _breakers[provider_name]


def build_fallback_chain(settings: Settings, http: Http) -> list[SearchProvider]:
    chain: list[SearchProvider] = []
    for cls in (
        BraveProvider,
        TavilyProvider,
        ExaProvider,
        XApiProvider,
        ArxivProvider,
        GithubProvider,
        XOsintProvider,
        MetaOsintProvider,
        SearXNGProvider,
        DdgProvider,
    ):
        provider = cls(settings, http)
        if provider.available():
            chain.append(provider)
    return chain


async def _execute_provider(
    provider: SearchProvider,
    query: str,
    max_results: int,
    recency: str | None,
    provider_timeout: float | None = None,
) -> tuple[list[ProviderResult], str]:
    cb = get_circuit_breaker(provider.name)
    if not cb.allow_execution():
        # pyrefly: ignore [unexpected-keyword]
        _logger.warning("Skipping provider due to open circuit breaker", provider=provider.name)
        return [], provider.name
    try:
        coro = provider.search(query, max_results, recency)
        # Hard limit: yavaş/asılı provider tüm aramayı bloklayamaz (TimeoutError → failure)
        rows = await (asyncio.wait_for(coro, provider_timeout) if provider_timeout else coro)
        if rows:
            cb.record_success()
            return rows, provider.name
        # pyrefly: ignore [unexpected-keyword]
        _logger.debug("Provider returned empty results", provider=provider.name)
        return [], provider.name
    except Exception:
        cb.record_failure()
        # pyrefly: ignore [unexpected-keyword]
        _logger.debug(
            # pyrefly: ignore [unexpected-keyword]
            "Provider failed during search execution",
            # pyrefly: ignore [unexpected-keyword]
            provider=provider.name,
            exc_info=True,
        )
        return [], provider.name


async def search_with_fallback(
    providers: list[SearchProvider],
    query: str,
    max_results: int,
    recency: str | None,
    provider_timeout: float | None = None,
) -> tuple[list[ProviderResult], str]:
    for provider in providers:
        rows, name = await _execute_provider(
            provider, query, max_results, recency, provider_timeout
        )
        if rows:
            return rows, name
    return [], ""


async def search_parallel(
    providers: list[SearchProvider],
    query: str,
    max_results: int,
    recency: str | None,
    provider_timeout: float | None = None,
) -> tuple[list[ProviderResult], str]:
    if not providers:
        return [], ""
    tasks = [_execute_provider(p, query, max_results, recency, provider_timeout) for p in providers]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_rows: list[ProviderResult] = []
    used_providers: list[str] = []

    for res in results:
        if isinstance(res, tuple):
            rows, name = res
            if rows:
                all_rows.extend(rows)
                used_providers.append(name)

    provider_name_str = "+".join(used_providers) if used_providers else ""
    return all_rows, provider_name_str


async def search_fast(
    providers: list[SearchProvider],
    query: str,
    max_results: int,
    recency: str | None,
    provider_timeout: float | None = None,
) -> tuple[list[ProviderResult], str]:
    """Yarış modu: genel-web provider'ları paralel başlar, ilk dolu sonuç kazanır.

    Kazanan belirlenince kalan task'ler iptal edilir → tipik latency en hızlı
    provider kadar olur (parallel moddaki 'en yavaş' yerine).

    Niche provider'lar (arxiv, github, x_*, meta_*) genel sorgularda yarışı
    kazanıp alakasız sonuç dönmesin diye race'e alınmaz; yalnızca hiç genel-web
    provider'ı yoksa tüm provider'larla yarışılır.
    """
    candidates = [p for p in providers if p.general_web] or providers
    if not candidates:
        return [], ""
    tasks = [
        asyncio.ensure_future(_execute_provider(p, query, max_results, recency, provider_timeout))
        for p in candidates
    ]
    try:
        for fut in asyncio.as_completed(tasks):
            rows, name = await fut
            if rows:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                return rows, name
        return [], ""
    finally:
        await asyncio.gather(*tasks, return_exceptions=True)


__all__ = [
    "SearchProvider",
    "BraveProvider",
    "TavilyProvider",
    "DdgProvider",
    "SearXNGProvider",
    "ExaProvider",
    "ArxivProvider",
    "GithubProvider",
    "XApiProvider",
    "XOsintProvider",
    "MetaOsintProvider",
    "build_fallback_chain",
    "search_with_fallback",
    "search_parallel",
    "search_fast",
    "get_circuit_breaker",
]
