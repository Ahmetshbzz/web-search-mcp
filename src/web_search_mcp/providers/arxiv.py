from urllib.parse import quote
from xml.etree import ElementTree as ET

from web_search_mcp.models import ProviderResult
from web_search_mcp.providers.base import SearchProvider


class ArxivProvider(SearchProvider):
    name = "arxiv"
    general_web = False  # akademik makale indeksi — genel sorgularda race'e girmez

    def available(self) -> bool:
        return True

    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        encoded_query = quote(query)
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query=all:{encoded_query}&start=0&max_results={max_results}"
        )
        timeout = getattr(self.settings, "search_timeout", 10.0) if self.settings else 10.0
        xml_text = await self.http.get_text(url, request_timeout=timeout)
        if not xml_text:
            return []

        results: list[ProviderResult] = []
        try:
            root = ET.fromstring(xml_text)
            # Namespace for Atom feed
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                id_elem = entry.find("atom:id", ns)
                published_elem = entry.find("atom:published", ns)

                title = (
                    title_elem.text.strip().replace("\n", " ")
                    if title_elem is not None and title_elem.text
                    else ""
                )
                summary = (
                    summary_elem.text.strip().replace("\n", " ")
                    if summary_elem is not None and summary_elem.text
                    else ""
                )
                href = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                published = (
                    published_elem.text.strip()[:10]
                    if published_elem is not None and published_elem.text
                    else None
                )

                if title and href:
                    results.append(
                        ProviderResult(
                            href=href,
                            title=f"[ArXiv Paper] {title}",
                            body=summary[:1000],
                            published=published,
                        )
                    )
        except Exception:
            pass

        return results[:max_results]
