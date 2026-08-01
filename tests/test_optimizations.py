"""Optimizasyon regresyon testleri:

- Sayfa içeriği cache'i (fetch + search tekrar sorgularında HTTP çağrısı yapılmaz)
- extract_with_meta tek trafilatura geçişi
- Deep research sub-query paralelliği
- Normalize search cache key
- gather exception izolasyonu (tek sayfa hatası diğerlerini düşürmez)
"""

import asyncio

import pytest

from web_search_mcp import extractors
from web_search_mcp.cache import MemoryTTLCache
from web_search_mcp.config import Settings
from web_search_mcp.http import DocumentResult
from web_search_mcp.models import FetchPage, SearchHit
from web_search_mcp.research import DeepResearchEngine
from web_search_mcp.service import WebSearchService

PAYLOAD = {
    "web": {
        "results": [
            {"title": "A", "url": "https://a.com/1", "description": "d1"},
            {"title": "B", "url": "https://b.com/x", "description": "d2"},
        ]
    }
}


class CountingHttp:
    def __init__(self, payload: object = PAYLOAD):
        self._payload = payload
        self.get_json_calls = 0
        self.get_doc_calls = 0
        self.fail_urls: set[str] = set()

    async def get_json(self, url: str, **kwargs: object) -> object:
        self.get_json_calls += 1
        return self._payload

    async def get_document(
        self, url: str, request_timeout: float, **kwargs: object
    ) -> DocumentResult:
        self.get_doc_calls += 1
        if url in self.fail_urls:
            raise RuntimeError("boom")
        return DocumentResult(
            content="<html><body><article><p>hello cached content</p></article></body></html>",
            final_url=url,
            content_type="text/html",
            status_code=200,
        )


def _service(http: CountingHttp) -> WebSearchService:
    return WebSearchService(
        Settings(
            brave_api_key="k",
            tavily_api_key="",
            exa_api_key="",
            searxng_base_url="",
            search_mode="fallback",
        ),
        http=http,
        cache=MemoryTTLCache(),
    )


@pytest.mark.asyncio
async def test_fetch_uses_page_cache():
    http = CountingHttp()
    service = _service(http)

    page1 = await service.fetch("https://example.com/page")
    page2 = await service.fetch("https://example.com/page")

    assert page1.status == "ok" and page2.status == "ok"
    assert page1.text == page2.text
    assert http.get_doc_calls == 1  # ikinci fetch cache'den geldi


@pytest.mark.asyncio
async def test_fetch_unreachable_not_cached():
    http = CountingHttp()
    service = _service(http)

    async def none_doc(url: str, request_timeout: float, **kwargs: object) -> None:
        http.get_doc_calls += 1
        return None

    http.get_document = none_doc  # type: ignore[method-assign]
    page1 = await service.fetch("https://example.com/down")
    page2 = await service.fetch("https://example.com/down")

    assert page1.status == "unreachable" and page2.status == "unreachable"
    assert http.get_doc_calls == 2  # başarısızlık cache'lenmez


@pytest.mark.asyncio
async def test_search_pages_cached_across_calls():
    http = CountingHttp()
    service = _service(http)

    hits1, _ = await service.search("q", max_results=5, fetch_pages=True)
    hits2, _ = await service.search("q", max_results=5, fetch_pages=True)

    assert len(hits1) == len(hits2) == 2
    assert http.get_json_calls == 1  # provider sonuçları cache'den
    assert http.get_doc_calls == 2  # top sayfalar yalnızca ilk çağrıda fetch edildi
    # İkinci çağrıda da sayfa içerikleri (snippet değil) dönmeli
    assert "hello cached content" in hits2[0].body


@pytest.mark.asyncio
async def test_search_cache_key_normalized():
    http = CountingHttp()
    service = _service(http)

    await service.search("  AsyncIO   Internals ", max_results=5, fetch_pages=False)
    await service.search("asyncio internals", max_results=5, fetch_pages=False)

    assert http.get_json_calls == 1


@pytest.mark.asyncio
async def test_gather_exception_isolation():
    http = CountingHttp()
    http.fail_urls.add("https://a.com/1")
    service = _service(http)

    hits, _ = await service.search("q", max_results=5, fetch_pages=True)

    assert len(hits) == 2
    # Patlayan sayfa snippet'e düşer, sağlam sayfanın içeriği korunur
    bodies = {hit.href: hit.body for hit in hits}
    assert "hello cached content" in bodies["https://b.com/x"]


def test_extract_with_meta_single_trafilatura_call(monkeypatch):
    calls = {"n": 0}
    real_extract = extractors.trafilatura.extract

    def counting_extract(*args, **kwargs):
        calls["n"] += 1
        return real_extract(*args, **kwargs)

    monkeypatch.setattr(extractors.trafilatura, "extract", counting_extract)

    html = (
        "<html><body><article><h1>Title</h1>"
        "<p>Enough content here for trafilatura to extract something.</p>"
        "</article></body></html>"
    )
    text, _ = extractors.extract_with_meta(html, "https://example.com", output_format="text")
    assert text
    assert calls["n"] == 1  # eskiden 2 çağrı yapılıyordu

    calls["n"] = 0
    md, _ = extractors.extract_with_meta(html, "https://example.com", output_format="markdown")
    assert md
    assert calls["n"] == 1


def test_extract_contacts_combined_regex():
    html = """
    <a href="https://wa.me/905551234567">WA</a>
    <a href="tel:+90 555 987 65 43">Call</a>
    <a href="mailto:info@example.com?subject=Hi">Mail</a>
    <a href="https://t.me/somechannel">TG</a>
    <a href="https://github.com/owner/repo">GH</a>
    <a href="https://www.linkedin.com/in/jane">LI</a>
    <a href="https://x.com/jack">X</a>
    <a href="https://instagram.com/jane">IG</a>
    <a href="https://wa.me/905551234567">WA dup</a>
    """
    contacts = extractors.extract_contacts_and_socials(html)
    assert contacts["whatsapp"] == ["+905551234567"]
    assert contacts["phone"] == ["+905559876543"]
    assert contacts["email"] == ["info@example.com"]
    assert contacts["telegram"] == ["https://t.me/somechannel"]
    assert "https://github.com/owner/repo" in contacts["socials"]
    assert "https://www.linkedin.com/in/jane" in contacts["socials"]
    assert "https://x.com/jack" in contacts["socials"]
    assert "https://instagram.com/jane" in contacts["socials"]


class _ParallelFakeService(WebSearchService):
    def __init__(self):
        super().__init__(
            Settings(brave_api_key="", tavily_api_key="", exa_api_key="", searxng_base_url="")
        )
        self.active = 0
        self.max_active = 0

    async def search(self, query, **kwargs):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.05)
        self.active -= 1
        from urllib.parse import quote

        return [
            SearchHit(title=query, href=f"https://example.com/{quote(query)}", body="body text")
        ], "fake"

    async def fetch(self, url, output_format="markdown"):
        return FetchPage(status="ok", text="hop2 content")


@pytest.mark.asyncio
async def test_research_subqueries_run_in_parallel():
    service = _ParallelFakeService()
    engine = DeepResearchEngine(service)

    res = await engine.execute_research(topic="test topic", depth=1)

    assert "# Deep Research Dossier: test topic" in res
    assert service.max_active == 3  # sıralı olsaydı 1 olurdu
