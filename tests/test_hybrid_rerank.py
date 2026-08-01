from web_search_mcp.models import EnrichedResult
from web_search_mcp.vector_rerank import compute_bm25_score, hybrid_rrf_rerank


def test_bm25_score():
    query = "Python GIL"
    text1 = "Python has a global interpreter lock known as the GIL."
    text2 = "Java has threads without a global lock."

    s1 = compute_bm25_score(query, text1)
    s2 = compute_bm25_score(query, text2)

    assert s1 > s2


def test_hybrid_rrf_rerank():
    results = [
        EnrichedResult(
            title="Java", href="https://java.com", snippet="Java overview", content="No GIL here"
        ),
        EnrichedResult(
            title="Python GIL",
            href="https://python.org",
            snippet="CPython GIL removal",
            content="PEP 703 removes GIL",
        ),
    ]

    reranked = hybrid_rrf_rerank(results, query="Python GIL PEP 703")
    assert reranked[0].title == "Python GIL"
