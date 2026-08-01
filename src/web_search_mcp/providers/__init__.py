from web_search_mcp.config import Settings
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult
from web_search_mcp.observability import get_logger
from web_search_mcp.providers.base import SearchProvider
from web_search_mcp.providers.brave import BraveProvider
from web_search_mcp.providers.ddg import DdgProvider
from web_search_mcp.providers.tavily import TavilyProvider

_logger = get_logger("providers")


def build_fallback_chain(settings: Settings, http: Http) -> list[SearchProvider]:
    chain: list[SearchProvider] = []
    for cls in (BraveProvider, TavilyProvider, DdgProvider):
        provider = cls(settings, http)
        if provider.available():
            chain.append(provider)
    return chain


async def search_with_fallback(
    providers: list[SearchProvider], query: str, max_results: int, recency: str | None
) -> tuple[list[ProviderResult], str]:
    """Sıralı dener; biri hata/boş dönerse SIRADAKİNE düşer."""
    for provider in providers:
        try:
            rows = await provider.search(query, max_results, recency)
            if rows:
                return rows, provider.name
            _logger.debug("provider %s returned no rows", provider.name)
        except Exception:  # noqa: BLE001 — provider hatası → sıradaki.
            _logger.debug("provider %s failed", provider.name, exc_info=True)
    return [], ""


__all__ = [
    "SearchProvider",
    "BraveProvider",
    "TavilyProvider",
    "DdgProvider",
    "build_fallback_chain",
    "search_with_fallback",
]
