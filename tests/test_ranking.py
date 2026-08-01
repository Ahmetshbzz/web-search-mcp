from web_search_mcp.models import EnrichedResult
from web_search_mcp.ranking import rank_results


def _hit(title: str, href: str, date: str = "") -> EnrichedResult:
    return EnrichedResult(title=title, href=href, snippet="", content="", date=date)


def test_rank_keeps_order_without_recency():
    hits = [_hit("a", "https://a.com"), _hit("b", "https://b.com")]
    assert rank_results(hits, None) == hits


def test_rank_by_date_then_authority():
    hits = [
        _hit("old", "https://example.org/x", "2020-01-01"),
        _hit("new", "https://example.com/y", "2024-01-01"),
    ]
    ranked = rank_results(hits, "week")
    assert ranked[0].title == "new"


def test_rank_authority_tiebreak_same_date():
    hits = [
        _hit("gov", "https://agency.gov/x", "2024-01-01"),
        _hit("com", "https://example.com/y", "2024-01-01"),
    ]
    ranked = rank_results(hits, "week")
    assert ranked[0].title == "gov"
