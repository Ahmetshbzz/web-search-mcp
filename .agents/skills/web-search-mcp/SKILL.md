---
name: web-search-mcp
description: Routing and operating rules for the web-search-mcp web intelligence engine. Use when a task needs live web data — searching (web/news/videos/images), reading pages, rendering JS-driven or social-profile pages, deep multi-hop research, structured field extraction, or site/llms.txt discovery — including tool selection, token-efficiency, and result-status fallback decisions. Applies to any agent connected to the web-search MCP server.
---

# Web Search MCP — Routing & Operating Rules

Pick the right tool by task class, keep token spend low, and react correctly to result statuses. Tools stay silent: never name them to the user; report findings, not machinery.

## Tool routing by task class

| Task class | Tool | Decision boundary |
| :--- | :--- | :--- |
| Current or changing facts (versions, prices, releases, news) | `web_search` with `recency` | If you already reliably know the answer, answer directly. For anything dated, you don't know it — search. |
| Single quick answer, latency-sensitive | `web_search` `mode="fast"` | Races general-web providers; niche sources (papers, repos, social) are excluded from the race — use `parallel` when those matter. |
| Broad multi-source coverage | `web_search` `mode="parallel"` (default) | Merges all providers with dedup and relevance rerank; costs more time and API calls than `fast`. |
| News-like queries | `web_search` `recency="day"` or `"week"` | A news endpoint fires alongside web results; freshest first. |
| Videos or images | `web_search_media` | Media endpoints, not page search — don't use for text answers. |
| One specific page | `web_fetch` | On long pages pass `query` and `max_chars` to get the relevant window instead of the whole document. |
| Live social profile timelines ("latest posts") | `web_render_page` | Search engines rank by engagement, not chronology — for timeline order, render the live DOM. Static pages don't need rendering. |
| Exhaustive multi-hop topic | `web_deep_research` | Expensive (many searches and fetches). Not for single-fact questions. |
| Official docs / API sites | `web_discover_site` first | If `llms.txt` / `llms-full.txt` exists, fetch it instead of crawling pages. |
| Named/typed fields from a page | `web_extract_structured` | Use when fields are required, not prose. |

## Token budgeting

- Start narrow: small `max_results` and `fetch_pages=false` for link scouting; widen only when insufficient.
- When the question is specific, always pass `query` on `web_fetch` — the server returns the matching window, not the full page.
- `response_format="json"` returns stable `S1..Sn` citation ids; use it when results feed further programmatic steps, plain text otherwise.

## Result statuses — how to react

- `blocked` → private/invalid URL; don't retry, pick another source.
- `unreachable` → site down or bot throttling; retry once, or try `web_render_page`.
- `empty` → page fetched but no readable text; try `web_render_page` for JS-heavy sites.
- `too_large` → over the size cap; re-fetch with a narrower `query`.
- `binary` → non-text payload; don't parse as text.
- 429 / transient provider errors → retry once, then proceed with what you have.

## Operating rules

1. Cite sources as markdown links from the returned list; never invent URLs.
2. Trust the date metadata in results over your own memory; when no date exists, say freshness is unverified instead of guessing.
3. Batch independent tool calls in one turn; serialize only when one call's input depends on another's output.
4. Bound your own loop: if two searches didn't move the answer forward, synthesize what you have and state what's missing.

