import json
import re
from typing import Any

from web_search_mcp.observability import get_logger
from web_search_mcp.service import WebSearchService

_logger = get_logger("structured")


class StructuredExtractor:
    def __init__(self, service: WebSearchService) -> None:
        self.service = service

    async def extract_structured_data(
        self,
        url: str,
        schema_description: str,
    ) -> dict[str, Any]:
        """Verilen URL'den belirtilen şemaya uygun yapılandırılmış JSON verisi çıkarır."""
        page = await self.service.fetch(url, output_format="text")
        if page.status != "ok" or not page.text:
            return {"error": f"Failed to fetch content from URL: {url}", "status": page.status}

        extracted_fields = self._parse_fields_from_schema(schema_description)
        result: dict[str, Any] = {
            "source_url": url,
            "publish_date": page.date,
            "extracted_data": {},
        }

        for field in extracted_fields:
            value = self._extract_field_value(page.text, field)
            result["extracted_data"][field] = value

        return result

    @staticmethod
    def _parse_fields_from_schema(schema_description: str) -> list[str]:
        # Simple extraction of field names from schema text or JSON keys
        if "{" in schema_description and "}" in schema_description:
            try:
                parsed = json.loads(schema_description)
                if isinstance(parsed, dict):
                    return list(parsed.keys())
            except Exception:
                pass

        fields = [
            f.strip(" :'\"") for f in re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", schema_description)
        ]
        return list(dict.fromkeys(fields))[:10]

    @staticmethod
    def _extract_field_value(text: str, field: str) -> str | None:
        pattern = re.compile(rf"{re.escape(field)}[\s:]+([^\n\.,;]+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()

        # Fallback keyword line match
        for line in text.split("\n"):
            if field.lower() in line.lower():
                return line.strip()[:200]

        return None
