---
name: web-search-mcp
description: Senior guidance and tool selection rules for web-search-mcp engine (web_search, web_fetch, web_discover_site, web_render_page, web_deep_research, web_extract_structured). Teaches agents when to use headless Chromium rendering (web_render_page) versus parallel search engines (web_search) for live social media timelines and JS SPAs.
---

# Web Search MCP - Agent Operating Standard & Skill

This skill defines the optimal tool selection, workflow rules, and best practices for agents using the `web-search-mcp` server.

## Tool Selection Matrix

| Objective | Recommended Tool | Rationale |
| :--- | :--- | :--- |
| **Strict Chronological Social Profile Timeline** (e.g. X/Twitter `@username`, LinkedIn, Instagram) | `web_render_page` | **CRITICAL:** Search engines (`web_search`) rank posts by relevance and viral engagement, not strict timeline order. `web_render_page` executes JavaScript via Playwright headless Chromium and renders the live DOM to extract exact current posts in chronological order. |
| **Broad Multi-Engine Query** (News, Documentation, Research) | `web_search` | Runs parallel search across Brave, Tavily, Exa, Arxiv, GitHub, X OSINT, and DDG with RRF reranking and deduplication. |
| **Deep Recursive Multi-Hop Investigation** | `web_deep_research` | Autonomous multi-query research agent for exhaustive topics. |
| **Structured JSON Data Extraction** | `web_extract_structured` | Extracts typed JSON schemas from web content. |
| **Site Metadata & LLM Index Discovery** | `web_discover_site` | Discovers `robots.txt`, `sitemap.xml`, `llms.txt`, and `llms-full.txt` index paths. |
| **Lightweight Single Page Reading** | `web_fetch` | Fast markdown conversion using TLS Chrome impersonation. |

---

## Core Rule: Social Media Live Profile Timelines

> [!IMPORTANT]
> **When an agent is asked to check a specific user's latest posts on social platforms (e.g., "Check Andrej Karpathy's last 2 posts on X"):**
> DO NOT rely solely on `web_search`.
> **ALWAYS use `web_render_page(url="https://x.com/username")`.**
> 
> **Why?**
> A profile's exact current feed is dynamically generated via JavaScript and updated in real-time. `web_render_page` launches Playwright headless Chromium, waits for `domcontentloaded` or `networkidle`, and extracts the exact live DOM tree. This guarantees 100% accurate, line-for-line matches with what a human user sees in their browser.

---

## Tool Usage Snippets & Parameters

### 1. `web_render_page` (Headless Chromium)
Use for JS SPAs, Shadow DOM content, and live social media profile timelines.
```json
{
  "url": "https://x.com/karpathy",
  "wait_until": "domcontentloaded",
  "capture_network": true,
  "extract_shadow_dom": true
}
```

### 2. `web_search` (Parallel Multi-Engine Reranked Search)
Use for broad inquiries, news, and technical topics.
```json
{
  "query": "Python 3.14 free-threaded GIL status",
  "max_results": 5,
  "output_format": "markdown"
}
```

### 3. `web_discover_site` (LLM Index Discovery)
Use to check if a website exposes structured AI entry points (`llms.txt` / `llms-full.txt`).
```json
{
  "domain_or_url": "docs.x.com"
}
```
