from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

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
    version="1.1.0",
    instructions=(
        "Web search and fetch server. Use web_search to find current information on the "
        "internet (it also fetches and cleans the top pages), and web_fetch to read a "
        "specific URL. Brave/Tavily API keys are used when configured, otherwise it "
        "falls back to DuckDuckGo."
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
        "Search the web and return cleaned, ready-to-read results. Uses Brave or Tavily "
        "when API keys are configured, otherwise DuckDuckGo. The top results' actual "
        "pages are fetched and their main content extracted (with publish dates), so "
        "you usually don't need a second fetch call. Use recency for time-sensitive "
        "queries. Prefer several focused queries over one broad query."
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
) -> str:
    """Search the web.

    Args:
        query: Search query, in whatever language fits the question.
        max_results: Number of results (1-20, default 8).
        recency: Optional freshness filter: 'day', 'week', 'month' or 'year'. Use for
            news/current versions/prices.
        fetch_pages: Fetch and clean the top pages' full text (default true).
    """
    sources, provider = await get_service().search(query, max_results, recency, fetch_pages)
    if not sources:
        return "No results found (or search providers unreachable)."
    return _format_sources(sources, provider)


@mcp.tool(
    name="web_fetch",
    title="Web Fetch",
    description=(
        "Fetch a URL and return its clean main text (article content without nav/ads/"
        "footer) plus the publish date when detectable. Local/private network targets "
        "are blocked. Use after web_search when you need a page's full content."
    ),
    annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True
    ),
)
async def web_fetch(url: str) -> str:
    """Fetch one URL and extract its main content.

    Args:
        url: Full http(s) URL to fetch.
    """
    page = await get_service().fetch(url)
    if page.status == "blocked":
        return f"Blocked or invalid URL: {url} (only public http/https URLs are allowed)"
    if page.status == "unreachable":
        return f"Could not fetch: {url}"
    if page.status == "empty":
        return f"Fetched but no readable content found: {url}"
    header = f"Source: {hostname(url)}" + (f" · {page.date}" if page.date else "")
    return f"{header}\n\n{truncate(page.text, get_settings().max_content_chars)}"


def main() -> None:
    mcp.run(transport="stdio")
