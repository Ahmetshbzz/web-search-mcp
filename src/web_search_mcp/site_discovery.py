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
        """Bir sitenin robots.txt, sitemap.xml, llms.txt ve llms-full.txt dosyalarını keşfeder."""
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
        llms_full_task = self.http.get_text(f"{base_url}/llms-full.txt", request_timeout=8.0)
        sitemap_task = self.http.get_text(f"{base_url}/sitemap.xml", request_timeout=8.0)

        robots_txt, llms_txt_data, llms_full_txt, sitemap_xml = await asyncio.gather(
            robots_task, llms_task, llms_full_task, sitemap_task, return_exceptions=True
        )

        robots_content = robots_txt if isinstance(robots_txt, str) else None
        sitemap_content = sitemap_xml if isinstance(sitemap_xml, str) else None
        llms_full_content = llms_full_txt if isinstance(llms_full_txt, str) else None

        extracted_sitemaps = self._extract_sitemaps_from_robots(robots_content)

        return {
            "target_site": base_url,
            "has_robots_txt": bool(robots_content),
            "robots_txt": robots_content[:3000] if robots_content else None,
            "has_llms_txt": bool(llms_txt_data and llms_txt_data.get("main")),
            "llms_txt": llms_txt_data.get("main", "")[:4000] if llms_txt_data else None,
            "has_llms_full_txt": bool(llms_full_content),
            "llms_full_preview": llms_full_content[:2000] if llms_full_content else None,
            "section_llms_indexes": llms_txt_data.get("sections", []) if llms_txt_data else [],
            "has_sitemap_xml": bool(sitemap_content or extracted_sitemaps),
            "sitemaps_found": extracted_sitemaps
            or ([f"{base_url}/sitemap.xml"] if sitemap_content else []),
        }

    async def _fetch_llms_txt(self, base_url: str) -> dict[str, Any]:
        paths = [
            "/llms.txt",
            "/llm.txt",
            "/.well-known/llms.txt",
            "/x-api/llms.txt",
            "/enterprise-api/llms.txt",
            "/x-ads-api/llms.txt",
            "/xdks/python/llms.txt",
        ]
        tasks = [self.http.get_text(f"{base_url}{p}", request_timeout=5.0) for p in paths]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        discovered_main: str | None = None
        discovered_sections: list[str] = []

        for p, res in zip(paths, results, strict=False):
            if isinstance(res, str) and len(res.strip()) > 10:
                if p == "/llms.txt" or not discovered_main:
                    discovered_main = res
                discovered_sections.append(f"{base_url}{p}")

        return {"main": discovered_main, "sections": discovered_sections}

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
