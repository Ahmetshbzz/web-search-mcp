import asyncio
from typing import Any
from urllib.parse import urlparse

from web_search_mcp.http import Http
from web_search_mcp.observability import get_logger

_logger = get_logger("site_discovery")


class SiteDiscoveryEngine:
    def __init__(self, http: Http) -> None:
        self.http = http

    async def discover(self, target_url_or_domain: str) -> dict[str, Any]:
        """Bir sitenin robots.txt, sitemap.xml ve llms.txt dosyalarını keşfeder."""
        url_raw = target_url_or_domain.strip()
        if not url_raw.startswith(("http://", "https://")):
            url_raw = f"https://{url_raw}"

        parsed = urlparse(url_raw)
        scheme = parsed.scheme or "https"
        host = parsed.netloc or parsed.path
        base_url = f"{scheme}://{host}"

        _logger.info("Discovering site metadata for %s", base_url)

        # Parallel discovery tasks
        robots_task = self.http.get_text(f"{base_url}/robots.txt", request_timeout=8.0)
        llms_task = self._fetch_llms_txt(base_url)
        sitemap_task = self.http.get_text(f"{base_url}/sitemap.xml", request_timeout=8.0)

        robots_txt, llms_txt, sitemap_xml = await asyncio.gather(
            robots_task, llms_task, sitemap_task, return_exceptions=True
        )

        robots_content = robots_txt if isinstance(robots_txt, str) else None
        llms_content = llms_txt if isinstance(llms_txt, str) else None
        sitemap_content = sitemap_xml if isinstance(sitemap_xml, str) else None

        extracted_sitemaps = self._extract_sitemaps_from_robots(robots_content)

        return {
            "target_site": base_url,
            "has_robots_txt": bool(robots_content),
            "robots_txt": robots_content[:3000] if robots_content else None,
            "has_llms_txt": bool(llms_content),
            "llms_txt": llms_content[:4000] if llms_content else None,
            "has_sitemap_xml": bool(sitemap_content or extracted_sitemaps),
            "sitemaps_found": extracted_sitemaps
            or ([f"{base_url}/sitemap.xml"] if sitemap_content else []),
        }

    async def _fetch_llms_txt(self, base_url: str) -> str | None:
        paths = [
            "/llms.txt",
            "/llm.txt",
            "/.well-known/llms.txt",
            "/llms-full.txt",
        ]
        for p in paths:
            content = await self.http.get_text(f"{base_url}{p}", request_timeout=6.0)
            if content and len(content.strip()) > 10:
                return content
        return None

    @staticmethod
    def _extract_sitemaps_from_robots(robots_txt: str | None) -> list[str]:
        if not robots_txt:
            return []
        sitemaps: list[str] = []
        for line in robots_txt.splitlines():
            if line.lower().startswith("sitemap:"):
                sm = line.split(":", 1)[1].strip()
                if sm:
                    sitemaps.append(sm)
        return list(dict.fromkeys(sitemaps))
