"""Subword semantic matching testleri — keyword körü olduğu kanıtlanan 3 vaka:

1. Morfoloji/tire: "nogil" ~ "no-GIL"
2. Kısaltma: "GIL" ~ "global interpreter lock"
3. Türkçe morfoloji: "kitap" ~ "kitaplarımda"
"""

from web_search_mcp.extractors import chunk_relevant_text
from web_search_mcp.models import EnrichedResult
from web_search_mcp.similarity import (
    char_ngrams,
    expand_query_terms,
    ngram_similarity,
)
from web_search_mcp.vector_rerank import compute_bm25_score, hybrid_rrf_rerank


def test_expand_query_abbreviation():
    terms = expand_query_terms("GIL")
    assert {"global", "interpreter", "lock"} <= terms


def test_expand_query_reverse():
    assert "k8s" in expand_query_terms("kubernetes networking")


def test_char_ngrams_subword_overlap():
    # "kitap" trigram'ları "kitaplarımda" içinde bulunur
    assert char_ngrams("kitap") & char_ngrams("kitaplarımda bu konu")


def test_ngram_similarity_morphology():
    assert ngram_similarity("kitap", "kitaplarımda anlatılır") > ngram_similarity(
        "kitap", "arabadan bahseder"
    )


def test_chunk_finds_nogil_section():
    text = ("lorem ipsum dolor sit amet " * 50) + (
        "\n\nThe no-GIL free-threaded build removes the global interpreter lock."
    )
    out = chunk_relevant_text(text, "nogil", 200)
    assert "no-GIL" in out


def test_chunk_finds_turkish_morphology():
    text = ("bos paragraf " * 40) + "\n\nkitaplarımda bu konu detaylı anlatılır"
    out = chunk_relevant_text(text, "kitap", 150)
    assert "kitaplarımda" in out


def test_bm25_abbreviation_expansion():
    score = compute_bm25_score("GIL removal", "the global interpreter lock was removed")
    assert score > 0.0  # eskiden 0.0'dı (kör)


def test_rerank_abbreviation_beats_noise():
    results = [
        EnrichedResult(
            title="Cats overview", href="https://a.com", snippet="pets", content="fluffy cats"
        ),
        EnrichedResult(
            title="CPython 3.13",
            href="https://b.com",
            snippet="release",
            content="the global interpreter lock can now be disabled",
        ),
    ]
    reranked = hybrid_rrf_rerank(results, query="disable GIL")
    assert reranked[0].href == "https://b.com"


def test_best_window_prefers_specific_version_region():
    """go.dev dogfood senaryosu: sayfa basi 'go1.26.0' ile doluyken
    'go1.26.5' sorgusu sayfanin sonundaki spesifik bolgeyi bulmali."""
    from web_search_mcp.extractors import _best_window

    top = "go1.26.0 (released 2026-02-10) major release notes. " * 30
    mid = "filler unrelated content about something else entirely. " * 60
    bottom = "go1.26.5 (released 2026-07-07) includes security fixes to crypto/tls. "
    text = top + "\n\n" + mid + "\n\n" + bottom

    out = _best_window(text, "go1.26.5 released security", 300)
    assert "go1.26.5" in out
    assert "2026-07-07" in out
    assert "go1.26.0" not in out
