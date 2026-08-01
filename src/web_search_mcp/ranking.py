from web_search_mcp.models import EnrichedResult
from web_search_mcp.urls import authority_score, hostname


def rank_results(results: list[EnrichedResult], recency: str | None) -> list[EnrichedResult]:
    """Tazelik-duyarlı sorguda tarih re-rank; yoksa provider'ın alaka sırasını korur."""
    if not recency:
        return results
    return sorted(
        results,
        key=lambda e: (e.date or "0000-00-00", authority_score(hostname(e.href))),
        reverse=True,
    )
