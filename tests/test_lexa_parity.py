"""Lexa WebFetch/WebSearch parity özellikleri + hız iyileştirmeleri testleri:

- HTTPS auto-upgrade
- Cross-host redirect raporlama (final_url)
- Markdown content-type passthrough (extraction atlanır)
- 10MB içerik sınırı (too_large)
- Binary içerik tespiti
- web_fetch query ile ilgili-bölüm chunking (token tasarrufu)
- web_fetch/web_search max_chars parametresi
- Citation reminder satırı
- search_fast yarış modu + per-provider hard timeout
"""

import asyncio
import time

import pytest

from web_search_mcp import mcp as mcp_module
from web_search_mcp.cache import MemoryTTLCache
from web_search_mcp.config import Settings
from web_search_mcp.http import DocumentResult
from web_search_mcp.models import FetchPage, ProviderResult
from web_search_mcp.providers import search_fast, search_parallel
from web_search_mcp.providers.base import SearchProvider
from web_search_mcp.service import WebSearchService


class DocHttp:
    """get_document çağrılarını kaydeden esnek fake."""

    def __init__(self, doc: DocumentResult | None = None):
        self.doc = doc or DocumentResult(
            content="<html><body><p>content</p></body></html>",
            final_url="",
            content_type="text/html",
            status_code=200,
        )
        self.urls: list[str] = []

    async def get_document(
        self, url: str, request_timeout: float, **kwargs: object
    ) -> DocumentResult:
        self.urls.append(url)
        if self.doc.final_url == "":
            self.doc.final_url = url
        return self.doc

    async def get_json(self, url: str, **kwargs: object) -> object:
        return {"web": {"results": []}}


def _service(http: DocHttp, **kw: object) -> WebSearchService:
    return WebSearchService(
        Settings(brave_api_key="", tavily_api_key="", exa_api_key="", searxng_base_url="", **kw),
        http=http,
        cache=MemoryTTLCache(),
    )


@pytest.mark.asyncio
async def test_https_auto_upgrade():
    http = DocHttp()
    service = _service(http)
    page = await service.fetch("http://example.com/page")
    assert page.status == "ok"
    assert http.urls[0].startswith("https://")


@pytest.mark.asyncio
async def test_cross_host_redirect_reported():
    doc = DocumentResult(
        content="<html><body><p>content here</p></body></html>",
        final_url="https://cdn.other.com/page",
        content_type="text/html",
        status_code=200,
    )
    http = DocHttp(doc)
    service = _service(http)
    page = await service.fetch("https://example.com/page")
    assert page.status == "ok"
    assert page.final_url == "https://cdn.other.com/page"


@pytest.mark.asyncio
async def test_markdown_passthrough_skips_extraction():
    md = "# Direct Markdown\n\nServed as markdown, no extraction needed."
    doc = DocumentResult(
        content=md, final_url="", content_type="text/markdown; charset=utf-8", status_code=200
    )
    http = DocHttp(doc)
    service = _service(http)
    page = await service.fetch("https://example.com/readme")
    assert page.status == "ok"
    assert "# Direct Markdown" in page.text  # trafilatura'ya uğramadı


@pytest.mark.asyncio
async def test_too_large_content():
    doc = DocumentResult(content=None, final_url="", content_type="text/html", too_large=True)
    http = DocHttp(doc)
    service = _service(http)
    page = await service.fetch("https://example.com/huge")
    assert page.status == "too_large"


@pytest.mark.asyncio
async def test_binary_content_detected():
    doc = DocumentResult(
        content=b"PK\x03\x04binary", final_url="", content_type="application/zip", status_code=200
    )
    http = DocHttp(doc)
    service = _service(http)
    page = await service.fetch("https://example.com/archive.zip")
    assert page.status == "binary"


@pytest.mark.asyncio
async def test_web_fetch_query_chunking(monkeypatch):
    long_text = (
        "Python 3.14 introduced template strings.\n\n"
        + ("Filler paragraph about unrelated cooking recipes and gardening tips. " * 30)
        + "\n\nRust 1.90 shipped async closures improvements."
    )

    class FakeSvc:
        async def fetch(self, url: str, output_format: str = "text") -> FetchPage:
            return FetchPage(status="ok", text=long_text, final_url=url)

    monkeypatch.setattr(mcp_module, "get_service", lambda: FakeSvc())
    out = await mcp_module.web_fetch(
        "https://example.com/x", query="Rust async closures", max_chars=200
    )
    assert "Rust 1.90" in out
    assert "cooking recipes" not in out  # alakasız bölüm elendi → token tasarrufu


@pytest.mark.asyncio
async def test_web_fetch_max_chars(monkeypatch):
    class FakeSvc:
        async def fetch(self, url: str, output_format: str = "text") -> FetchPage:
            return FetchPage(status="ok", text="word " * 500, final_url=url)

    monkeypatch.setattr(mcp_module, "get_service", lambda: FakeSvc())
    out = await mcp_module.web_fetch("https://example.com/x", max_chars=100)
    assert len(out) < 250  # header + ~100 char içerik


def test_citation_reminder_in_sources():
    from web_search_mcp.models import SearchHit

    out = mcp_module._format_sources([SearchHit(title="T", href="https://x.co", body="b")], "brave")
    assert "markdown links" in out


class _StubProvider(SearchProvider):
    def __init__(self, name: str, delay: float, rows: int = 1):
        self.name = name
        self.delay = delay
        self.rows = rows

    def available(self) -> bool:
        return True

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        await asyncio.sleep(self.delay)
        return [
            ProviderResult(title=f"{self.name}-{i}", href=f"https://{self.name}.com/{i}")
            for i in range(self.rows)
        ]


@pytest.mark.asyncio
async def test_search_fast_race_winner():
    fast = _StubProvider("fast", delay=0.01)
    slow = _StubProvider("slow", delay=0.6)

    t0 = time.perf_counter()
    rows, name = await search_fast([slow, fast], "q", 5, None)
    elapsed = time.perf_counter() - t0

    assert name == "fast"
    assert len(rows) == 1
    assert elapsed < 0.3  # slow provider'ı beklemedi


@pytest.mark.asyncio
async def test_provider_hard_timeout_in_parallel():
    good = _StubProvider("good", delay=0.01)
    hanging = _StubProvider("hanging", delay=5.0)

    t0 = time.perf_counter()
    rows, name = await search_parallel([hanging, good], "q", 5, None, provider_timeout=0.2)
    elapsed = time.perf_counter() - t0

    assert name == "good"
    assert len(rows) == 1
    assert elapsed < 1.0  # 5s'lik provider timeout'a takıldı, bloklamadı


@pytest.mark.asyncio
async def test_search_fast_all_empty_returns_none():
    empty = _StubProvider("empty", delay=0.01, rows=0)
    rows, name = await search_fast([empty], "q", 5, None)
    assert rows == []
    assert name == ""


def test_chunk_relevant_text_giant_paragraph_respects_limit():
    from web_search_mcp.extractors import chunk_relevant_text

    # Trafilatura tipik çıktısı: çift newline olmayan tek dev blok
    giant = ("word " * 2000) + "rust async closures shipped" + ("word " * 2000)
    out = chunk_relevant_text(giant, "rust closures", 500)
    assert len(out) <= 500
    assert "rust async closures" in out  # sorgu bölgesi pencereye girdi


def test_chunk_relevant_text_no_match_takes_head():
    from web_search_mcp.extractors import chunk_relevant_text

    giant = "word " * 3000
    out = chunk_relevant_text(giant, "nonexistent", 300)
    assert len(out) <= 300


class _SpecializedProvider(_StubProvider):
    general_web = False


@pytest.mark.asyncio
async def test_search_fast_excludes_niche_providers():
    # Niche provider aninda doner ama race'e alinmamali (dogfood bulgusu: arxiv vakasi)
    niche = _SpecializedProvider("arxiv_like", delay=0.0)
    general = _StubProvider("general", delay=0.05)

    rows, name = await search_fast([niche, general], "q", 5, None)

    assert name == "general"
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_search_fast_falls_back_when_all_niche():
    # Hic genel-web provider yoksa niche'lerle yarismaya devam et
    niche = _SpecializedProvider("arxiv_like", delay=0.01)

    rows, name = await search_fast([niche], "q", 5, None)

    assert name == "arxiv_like"
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_http_fallback_when_https_fails():
    """HTTPS upgrade basarisiz olursa orijinal http'ye dusulmeli (thinkbroadband vakasi)."""

    class HttpsFailHttp:
        async def get_document(self, url: str, request_timeout: float, **kwargs: object):
            if url.startswith("https://"):
                return None
            return DocumentResult(
                content="<html><body><p>plain http works</p></body></html>",
                final_url=url,
                content_type="text/html",
                status_code=200,
            )

        async def get_json(self, url: str, **kwargs: object) -> object:
            return {"web": {"results": []}}

    service = _service(HttpsFailHttp())
    page = await service.fetch("http://legacy.example.com/page")
    assert page.status == "ok"
    assert "plain http works" in page.text
