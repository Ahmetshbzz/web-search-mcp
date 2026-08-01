from web_search_mcp.models import EnrichedResult, ProviderResult
from web_search_mcp.urls import authority_score, canonical_url, hostname


def deduplicate_results(results: list[ProviderResult]) -> list[ProviderResult]:
    seen: set[str] = set()
    deduped: list[ProviderResult] = []
    for r in results:
        c_url = canonical_url(r.href)
        if c_url not in seen:
            seen.add(c_url)
            deduped.append(r)
    return deduped


def rank_results(results: list[EnrichedResult], recency: str | None) -> list[EnrichedResult]:
    """Tazelik-duyarlı sorguda tarih re-rank; yoksa provider'ın alaka sırasını korur."""
    if not recency:
        return results
    return sorted(
        results,
        key=lambda e: (e.date or "0000-00-00", authority_score(hostname(e.href))),
        reverse=True,
    )
