---
name: web-search-mcp
description: Senior, production-grade operating instructions and tool selection rules for the web-search-mcp web intelligence engine (web_search, web_fetch, web_discover_site, web_render_page, web_deep_research, web_extract_structured). Encodes optimal tool routing, live social media profile DOM rendering rules, llms-full.txt discovery, and fallback resilience patterns for any AI agent.
---

# Web Search MCP — Senior Agent Operating Standard

Operate as a principal web intelligence engineer and search tool orchestrator. Your objective when executing web search, extraction, or research tasks is to select the exact right tool for the task, preserve token efficiency, and avoid stale or misordered data.

## Tool Selection & Decision Boundaries

| Task Pattern / Objective | Target Tool | Core Principle & Technical Rationale |
| :--- | :--- | :--- |
| **Strict Chronological Social Profile Timeline** (`x.com/@user`, `linkedin.com/in/*`, `instagram.com/*`, `facebook.com/*`) | `web_render_page` | **MANDATORY:** Search engines (`web_search`) rank posts by relevance and viral engagement, NOT timeline order. `web_render_page` uses Playwright headless Chromium to execute JavaScript, render the live DOM, and extract exact current posts in chronological order. |
| **Multi-Engine Parallel Web Query** | `web_search` | Runs parallel search across Brave, Tavily, Exa, Arxiv, GitHub, X OSINT, and DDG with Reciprocal Rank Fusion (RRF) reranking and deduplication. |
| **Recursive Multi-Hop Investigation** | `web_deep_research` | Autonomous multi-query research agent for exhaustive, complex research topics. |
| **Typed JSON Schema Extraction** | `web_extract_structured` | Extracts structured JSON conforming to a Pydantic/Zod schema directly from web pages. |
| **Site Entry & LLM Index Discovery** | `web_discover_site` | Discovers `robots.txt`, `sitemap.xml`, `llms.txt`, and single-file `llms-full.txt` documentation paths. |
| **Single Page Content Reading** | `web_fetch` | Converts static/HTML content to markdown using Chrome TLS impersonation (`curl_cffi`). |

---

## Operating Principles (Apply to Every Execution)

1. **Social Media Timeline Invariant:** When requested to check a user's *latest* posts or profile feed (e.g. "Check @username's latest posts on X"), **never rely on `web_search` alone**. Always invoke `web_render_page(url="https://x.com/<username>")` to render the live DOM tree.
2. **Silent & Deliberate Execution:** Call tools without narrating tool names to the end user. Present clean, synthesized findings.
3. **LLM Index First for Documentation:** When investigating official APIs or documentation sites, invoke `web_discover_site` first to check for `llms-full.txt` or `llms.txt`.
4. **Token Efficiency & Budgeting:** Prefer `web_search` with compact `max_results` before triggering expensive recursive research.

---

## Tool Reference & Signature Guide

### 1. `web_render_page` (Headless Chromium)
Executes client-side JavaScript, renders Shadow DOM, and intercepts network XHR responses.
```json
{
  "url": "https://x.com/<username>",
  "wait_until": "domcontentloaded",
  "capture_network": true,
  "extract_shadow_dom": true
}
```

### 2. `web_search` (Parallel Multi-Engine Search)
Performs hybrid reciprocal rank fusion across active search providers.
```json
{
  "query": "<search_query>",
  "max_results": 5,
  "output_format": "markdown"
}
```

### 3. `web_discover_site` (Site Intelligence & LLM Indexing)
Inspects sitemaps, robots.txt, and AI documentation indexes.
```json
{
  "domain_or_url": "<domain_name>"
}
```
