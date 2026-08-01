import math
import re

from web_search_mcp.models import EnrichedResult


def compute_bm25_score(query: str, text: str, k1: float = 1.5, b: float = 0.75) -> float:
    q_words = set(re.findall(r"\w+", query.lower()))
    if not q_words or not text.strip():
        return 0.0

    t_words = re.findall(r"\w+", text.lower())
    if not t_words:
        return 0.0

    doc_len = len(t_words)
    avg_len = 100.0  # reference avg document length
    score = 0.0

    for word in q_words:
        tf = t_words.count(word)
        if tf > 0:
            idf = math.log((1 + 1) / (1 + 0.5)) + 1.0
            num = tf * (k1 + 1)
            den = tf + k1 * (1 - b + b * (doc_len / avg_len))
            score += idf * (num / den)

    return score


def hybrid_rrf_rerank(
    results: list[EnrichedResult], query: str, rrf_k: int = 60
) -> list[EnrichedResult]:
    """BM25 ve Tazelik (Recency) skorlarını RRF (Reciprocal Rank Fusion) ile birleştirir."""
    if not results or not query.strip():
        return results

    # Score 1: BM25 score
    bm25_scored = [
        (idx, compute_bm25_score(query, f"{r.title} {r.snippet} {r.content}"))
        for idx, r in enumerate(results)
    ]
    bm25_scored.sort(key=lambda x: x[1], reverse=True)
    bm25_ranks = {item[0]: rank for rank, item in enumerate(bm25_scored, 1)}

    # RRF Score calculation
    rrf_scores: list[tuple[int, float]] = []
    for idx in range(len(results)):
        rank_bm25 = bm25_ranks.get(idx, len(results))
        score = 1.0 / (rrf_k + rank_bm25)
        rrf_scores.append((idx, score))

    rrf_scores.sort(key=lambda x: x[1], reverse=True)
    return [results[idx] for idx, _ in rrf_scores]
