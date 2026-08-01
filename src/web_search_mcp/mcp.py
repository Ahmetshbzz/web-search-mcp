import json
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import PromptMessage, TextContent, ToolAnnotations

from web_search_mcp.browser_render import BrowserRenderEngine
from web_search_mcp.config import get_settings
from web_search_mcp.extractors import chunk_relevant_text
from web_search_mcp.models import SearchHit
from web_search_mcp.research import DeepResearchEngine
from web_search_mcp.service import WebSearchService
from web_search_mcp.site_discovery import SiteDiscoveryEngine
from web_search_mcp.structured import StructuredExtractor
from web_search_mcp.text import truncate
from web_search_mcp.urls import hostname

_service: WebSearchService | None = None
_research_engine: DeepResearchEngine | None = None
_structured_extractor: StructuredExtractor | None = None
_site_discovery_engine: SiteDiscoveryEngine | None = None
_browser_render_engine: BrowserRenderEngine | None = None


def get_service() -> WebSearchService:
    global _service
    if _service is None:
        _service = WebSearchService(get_settings())
    return _service


def get_research_engine() -> DeepResearchEngine:
    global _research_engine
    if _research_engine is None:
        _research_engine = DeepResearchEngine(get_service())
    return _research_engine


def get_structured_extractor() -> StructuredExtractor:
    global _structured_extractor
    if _structured_extractor is None:
        _structured_extractor = StructuredExtractor(get_service())
    return _structured_extractor


def get_site_discovery_engine() -> SiteDiscoveryEngine:
    global _site_discovery_engine
    if _site_discovery_engine is None:
        _site_discovery_engine = SiteDiscoveryEngine(get_service().http)
    return _site_discovery_engine


def get_browser_render_engine() -> BrowserRenderEngine:
    global _browser_render_engine
    if _browser_render_engine is None:
        _browser_render_engine = BrowserRenderEngine()
    return _browser_render_engine


mcp = MCPServer(
    name="web-search",
    version="3.1.0",
    instructions=(
        "Web search & intelligence server with multi-provider aggregation "
        "(Brave, Tavily, Exa, ArXiv, GitHub, SearXNG, DDG) in parallel/fallback/fast-race "
        "modes, Chrome TLS fingerprinting, query-aware content chunking for token-efficient "
        "fetching, markdown-first content negotiation, HTTPS upgrade, cross-host redirect "
        "reporting, 10MB streaming size caps, binary detection, autonomous multi-hop deep "
        "research, structured JSON data extraction, headless browser rendering "
        "(Playwright/Shadow DOM/Network), site discovery (robots.txt, sitemap.xml, "
        "llms.txt), local OCR canvas extraction, Markdown/PDF extraction, and two-tier "
        "caching (in-memory LRU + SQLite)."
    ),
)


def _format_sources(sources: list[SearchHit], provider: str) -> str:
    lines = [f"Provider: {provider}", ""]
    for i, s in enumerate(sources, 1):
        title = s.title or s.href
        label = f" [{s.label}]" if s.label else ""
        lines.append(f"[{i}] {title}{label}")
        lines.append(f"    {s.href}")
        body = (s.body or "").strip()
        if body:
            lines.append(f"    {body}")
        lines.append("")
    lines.append("Note: cite the sources above as markdown links [title](url) in your response.")
    return "\n".join(lines).strip()


def _format_sources_json(sources: list[SearchHit], provider: str, query: str) -> str:
    """Deterministik citation haritalı yapısal çıktı: agent [S1] id'siyle referans
    verip citations listesinden URL/başlık çözebilir."""
    results = []
    citations = []
    for i, s in enumerate(sources, 1):
        sid = f"S{i}"
        results.append(
            {
                "id": sid,
                "title": s.title or s.href,
                "url": s.href,
                "label": s.label,
                "body": (s.body or "").strip(),
            }
        )
        citations.append({"id": sid, "title": s.title or s.href, "url": s.href})
    return json.dumps(
        {"query": query, "provider": provider, "results": results, "citations": citations},
        indent=2,
    )


@mcp.tool(
    name="web_search",
    title="Web Search",
    description=(
        "Search the web and return cleaned results. Supports parallel search across "
        "Brave, Tavily, Exa, SearXNG, and DDG with deduplication and domain filtering."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_search(
    query: str,
    max_results: int = 8,
    recency: str | None = None,
    fetch_pages: bool = True,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    mode: str | None = None,
    output_format: Literal["text", "markdown"] = "text",
    max_chars: int | None = None,
    response_format: Literal["text", "json"] = "text",
) -> str:
    """Search the web with advanced filtering and extraction.

    mode: "parallel" (default, tüm provider'lar), "fallback" (sıralı),
    "fast" (yarış — genel-web provider'ları arasında ilk dolu sonuç kazanır,
    en düşük gecikme; niche kaynaklar için parallel/fallback kullan).
    response_format: "json" → S1..Sn id'li yapısal sonuç + citation haritası.
    """
    sources, provider = await get_service().search(
        query=query,
        max_results=max_results,
        recency=recency,
        fetch_pages=fetch_pages,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        mode=mode,
        output_format=output_format,
        max_content_chars=max_chars,
    )
    if not sources:
        return "No results found (or search providers unreachable)."
    if response_format == "json":
        return _format_sources_json(sources, provider, query)
    return _format_sources(sources, provider)


@mcp.tool(
    name="web_fetch",
    title="Web Fetch",
    description=(
        "Fetch a URL (HTML/PDF) using Chrome TLS impersonation and return clean text or Markdown."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_fetch(
    url: str,
    output_format: Literal["text", "markdown"] = "text",
    query: str | None = None,
    max_chars: int | None = None,
) -> str:
    """Fetch one URL and extract its main content (text or markdown).

    query verilirse sayfanın yalnızca sorguyla ilgili bölümleri döner (token tasarrufu).
    max_chars ile döndürülen içerik uzunluğu sınırlanabilir.
    """
    page = await get_service().fetch(url, output_format=output_format)
    if page.status == "blocked":
        return f"Blocked or invalid URL: {url} (only public http/https URLs are allowed)"
    if page.status == "unreachable":
        return f"Could not fetch: {url}"
    if page.status == "empty":
        return f"Fetched but no readable content found: {url}"
    if page.status == "too_large":
        limit_mb = get_settings().fetch_max_bytes // (1024 * 1024)
        return f"Content exceeds the {limit_mb} MB size limit: {url}"
    if page.status == "binary":
        return f"URL serves binary content that cannot be extracted as text: {url}"

    header = f"Source: {hostname(url)}" + (f" · {page.date}" if page.date else "")
    # Cross-host redirect bildirimi (Lexa parity)
    if page.final_url and hostname(page.final_url) != hostname(url):
        header += f" (redirected to {hostname(page.final_url)})"

    limit = max_chars or get_settings().max_content_chars
    if query and query.strip():
        body = chunk_relevant_text(page.text, query, limit)
    else:
        body = truncate(page.text, limit)
    return f"{header}\n\n{body}"


@mcp.tool(
    name="web_discover_site",
    title="Site Metadata & LLM Discovery",
    description=(
        "Discover and analyze a site's robots.txt, sitemap.xml, and llms.txt / llm.txt files."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_discover_site(url_or_domain: str) -> str:
    """Discover site metadata: robots.txt, sitemap.xml, and llms.txt."""
    data = await get_site_discovery_engine().discover(url_or_domain)
    return json.dumps(data, indent=2)


@mcp.tool(
    name="web_render_page",
    title="Headless Browser Page Renderer",
    description=(
        "Render a web page using headless Chromium (Playwright). Extracts full JS DOM, "
        "Shadow DOM text, WhatsApp/contacts, and intercepts XHR/GraphQL JSON responses."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_render_page(
    url: str,
    wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle",
    capture_network: bool = True,
    extract_shadow_dom: bool = True,
) -> str:
    """Render page with headless Chromium browser."""
    data = await get_browser_render_engine().render_page(
        url=url,
        wait_until=wait_until,
        capture_network=capture_network,
        extract_shadow_dom=extract_shadow_dom,
    )
    return json.dumps(data, indent=2)


@mcp.tool(
    name="web_deep_research",
    title="Web Deep Research Engine",
    description=(
        "Execute an autonomous multi-hop deep research investigation on a topic. "
        "Formulates sub-queries, navigates sub-links, extracts Markdown, and synthesizes a dossier."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_deep_research(topic: str, depth: int = 2) -> str:
    """Perform autonomous multi-hop deep research on a topic."""
    return await get_research_engine().execute_research(topic=topic, depth=depth)


@mcp.tool(
    name="web_extract_structured",
    title="Structured JSON Data Extractor",
    description=(
        "Fetch a web page and extract structured JSON objects matching a specified schema."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_extract_structured(url: str, schema_description: str) -> str:
    """Extract structured JSON objects from a web page."""
    data = await get_structured_extractor().extract_structured_data(
        url=url, schema_description=schema_description
    )
    return json.dumps(data, indent=2)


@mcp.resource(uri="search://cache/list", name="Cached Query Keys")
async def list_cache_keys() -> str:
    """Returns a list of currently active cached search query keys."""
    service = get_service()
    if hasattr(service.cache, "list_keys"):
        keys = await service.cache.list_keys()  # type: ignore[attr-defined]
        return json.dumps({"active_cached_keys": keys}, indent=2)
    return json.dumps({"active_cached_keys": []})


@mcp.prompt(name="deep-research", description="Conduct a deep, multi-query research on a topic.")
def prompt_deep_research(topic: str) -> list[PromptMessage]:
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=(
                    f"Please perform a deep, comprehensive research on '{topic}'.\n"
                    "1. Break the topic down into 3 targeted web_search queries.\n"
                    "2. Fetch full pages for top sources using web_fetch in markdown.\n"
                    "3. Synthesize a detailed summary with citations."
                ),
            ),
        )
    ]


@mcp.prompt(name="tech-version-check", description="Check current software release versions.")
def prompt_tech_version_check(library: str) -> list[PromptMessage]:
    return [
        PromptMessage(
            role="user",
            content=TextContent(
                type="text",
                text=(
                    f"Check the current 2026 release version and changelog for '{library}'.\n"
                    "Use web_search with recency='year' or 'month'."
                ),
            ),
        )
    ]


def main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(prog="web-search-mcp")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport protocol (env: MCP_TRANSPORT). HTTP modları hosted kullanım içindir.",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="HTTP transport bind adresi (env: MCP_HOST)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8000")),
        help="HTTP transport portu (env: MCP_PORT)",
    )
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port)
