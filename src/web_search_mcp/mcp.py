import json
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.types import Prompt, PromptMessage, TextContent, ToolAnnotations

from web_search_mcp.config import get_settings
from web_search_mcp.models import SearchHit
from web_search_mcp.service import WebSearchService
from web_search_mcp.text import truncate
from web_search_mcp.urls import hostname

_service: WebSearchService | None = None


def get_service() -> WebSearchService:
    global _service
    if _service is None:
        _service = WebSearchService(get_settings())
    return _service


mcp = MCPServer(
    name="web-search",
    version="1.2.0",
    instructions=(
        "Web search and fetch server with multi-provider parallel aggregation, domain filtering, "
        "Markdown/PDF extraction, and SQLite caching. Use web_search for queries and web_fetch for direct URLs."
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
    return "\n".join(lines).strip()


@mcp.tool(
    name="web_search",
    title="Web Search",
    description=(
        "Search the web and return cleaned, ready-to-read results. Supports parallel search across "
        "Brave, Tavily, Exa, SearXNG, and DDG with automatic deduplication, reranking, and domain filtering."
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
) -> str:
    """Search the web with advanced filtering and extraction."""
    sources, provider = await get_service().search(
        query=query,
        max_results=max_results,
        recency=recency,
        fetch_pages=fetch_pages,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        mode=mode,
        output_format=output_format,
    )
    if not sources:
        return "No results found (or search providers unreachable)."
    return _format_sources(sources, provider)


@mcp.tool(
    name="web_fetch",
    title="Web Fetch",
    description=(
        "Fetch a URL (HTML or PDF) and return clean main text or Markdown content plus publish date. "
        "Local and private network targets are blocked."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_fetch(
    url: str, output_format: Literal["text", "markdown"] = "text"
) -> str:
    """Fetch one URL and extract its main content (text or markdown)."""
    page = await get_service().fetch(url, output_format=output_format)
    if page.status == "blocked":
        return f"Blocked or invalid URL: {url} (only public http/https URLs are allowed)"
    if page.status == "unreachable":
        return f"Could not fetch: {url}"
    if page.status == "empty":
        return f"Fetched but no readable content found: {url}"
    header = f"Source: {hostname(url)}" + (f" · {page.date}" if page.date else "")
    return f"{header}\n\n{truncate(page.text, get_settings().max_content_chars)}"


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
                    "2. Fetch full pages for the top relevant sources using web_fetch in markdown format.\n"
                    "3. Synthesize a detailed summary with citations."
                ),
            ),
        )
    ]


@mcp.prompt(name="tech-version-check", description="Check current versions of software or libraries.")
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
    mcp.run(transport="stdio")
