from urllib.parse import parse_qs, quote, urlparse

from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class MetaDevProvider(SearchProvider):
    name = "meta_dev"

    def available(self) -> bool:
        return True

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        encoded = quote(f"site:developers.facebook.com {query}")
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        timeout = getattr(self.settings, "search_timeout", 10.0) if self.settings else 10.0

        html = await self.http.get_text(url, headers=headers, request_timeout=timeout)
        if not html:
            return []

        from lxml import html as lxml_html

        results: list[ProviderResult] = []
        try:
            tree = lxml_html.fromstring(f"<html><body>{html}</body></html>")
            # Select outer result containers
            xpath_expr = "//div[contains(@class, 'result') or contains(@class, 'result__body')]"
            nodes = tree.xpath(xpath_expr)
            for node in nodes:
                a_tags = node.xpath(".//a[contains(@class, 'result__url')]") or node.xpath(".//a")
                snippet_tags = node.xpath(".//*[contains(@class, 'snippet')]")
                if a_tags:
                    a = a_tags[0]
                    raw_href = a.get("href", "")
                    title = a.text_content().strip()
                    snippet = snippet_tags[0].text_content().strip() if snippet_tags else ""

                    target_url = raw_href
                    if "uddg=" in raw_href:
                        parsed = parse_qs(urlparse(raw_href).query)
                        target_url = parsed.get("uddg", [raw_href])[0]

                    if target_url and title and not any(r.href == target_url for r in results):
                        results.append(
                            ProviderResult(
                                href=target_url,
                                title=f"[Meta Dev API] {title}",
                                body=snippet,
                            )
                        )
        except Exception:
            pass

        return results[:max_results]
