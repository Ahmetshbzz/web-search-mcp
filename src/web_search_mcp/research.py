import asyncio
import re
from urllib.parse import urlparse

from web_search_mcp.models import SearchHit
from web_search_mcp.observability import get_logger
from web_search_mcp.service import WebSearchService

_logger = get_logger("research")


class DeepResearchEngine:
    def __init__(self, service: WebSearchService) -> None:
        self.service = service

    async def execute_research(
        self,
        topic: str,
        depth: int = 2,
        max_pages_per_hop: int = 3,
    ) -> str:
        """Otonom çok adımlı (multi-hop) derin araştırma yürütür."""
        topic = topic.strip()
        if not topic:
            return "Please provide a valid research topic."

        _logger.info("Starting deep research execution for topic '%s' (depth: %s)", topic, depth)

        # Step 1: Formulate sub-queries
        sub_queries = [
            topic,
            f"{topic} overview architecture specifications",
            f"{topic} history benchmarks comparison",
        ]

        all_hits: list[SearchHit] = []
        visited_urls: set[str] = set()

        # Step 2: Primary hop - tüm sub-query'ler paralel aranır
        search_results = await asyncio.gather(
            *[
                self.service.search(
                    query=query,
                    max_results=max_pages_per_hop,
                    fetch_pages=True,
                    output_format="markdown",
                )
                for query in sub_queries
            ],
            return_exceptions=True,
        )
        for res in search_results:
            if isinstance(res, Exception):
                _logger.debug("sub-query search failed", exc_info=res)
                continue
            hits, _ = res
            for hit in hits:
                if hit.href not in visited_urls:
                    visited_urls.add(hit.href)
                    all_hits.append(hit)

        # Step 3: Secondary hop - top hit'lerden çıkan sub-link'ler paralel fetch edilir
        secondary_hits: list[SearchHit] = []
        if depth > 1 and all_hits:
            sub_links = self._extract_sub_links(all_hits[:2])
            fresh_links: list[str] = []
            for link in sub_links:
                if len(fresh_links) >= max_pages_per_hop:
                    break
                if link not in visited_urls:
                    visited_urls.add(link)
                    fresh_links.append(link)

            pages = await asyncio.gather(
                *[self.service.fetch(link, output_format="markdown") for link in fresh_links],
                return_exceptions=True,
            )
            for link, page in zip(fresh_links, pages, strict=False):
                if isinstance(page, Exception):
                    _logger.debug("secondary hop fetch failed for %s", link, exc_info=page)
                    continue
                if page.status == "ok" and page.text:
                    domain = urlparse(link).netloc
                    secondary_hits.append(
                        SearchHit(
                            title=f"Deep Hop Source: {domain}",
                            href=link,
                            body=page.text[:4000],
                            label=f"{domain} · Hop 2",
                        )
                    )

        # Step 4: Synthesize Research Dossier
        return self._format_research_dossier(topic, all_hits, secondary_hits)

    @staticmethod
    def _extract_sub_links(hits: list[SearchHit]) -> list[str]:
        links: list[str] = []
        url_pattern = re.compile(r"https?://[^\s\"'>]+")
        for hit in hits:
            found = url_pattern.findall(hit.body)
            for u in found:
                u_clean = u.rstrip(").,;")
                if u_clean.startswith("http") and "wikipedia.org" not in u_clean:
                    links.append(u_clean)
        return list(dict.fromkeys(links))

    @staticmethod
    def _format_research_dossier(
        topic: str, primary_hits: list[SearchHit], secondary_hits: list[SearchHit]
    ) -> str:
        sections = [
            f"# Deep Research Dossier: {topic}",
            "",
            f"Total Primary Sources Explored: {len(primary_hits)}",
            f"Total Multi-Hop Sub-Sources Explored: {len(secondary_hits)}",
            "",
            "## Primary Findings & Key Sources",
            "",
        ]

        for idx, hit in enumerate(primary_hits, 1):
            sections.append(f"### [{idx}] {hit.title}")
            sections.append(f"**URL:** {hit.href}")
            if hit.label:
                sections.append(f"**Metadata:** {hit.label}")
            sections.append("")
            sections.append(hit.body)
            sections.append("---")
            sections.append("")

        if secondary_hits:
            sections.append("## Secondary Multi-Hop Deep Findings")
            sections.append("")
            for idx, hit in enumerate(secondary_hits, 1):
                sections.append(f"### [Hop 2.{idx}] {hit.title}")
                sections.append(f"**URL:** {hit.href}")
                sections.append(hit.body[:2000])
                sections.append("---")
                sections.append("")

        return "\n".join(sections)
