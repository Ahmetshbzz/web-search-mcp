from abc import ABC, abstractmethod

from web_search_mcp.config import Settings
from web_search_mcp.http import Http
from web_search_mcp.models import ProviderResult


class SearchProvider(ABC):
    name: str = ""
    # Genel web araması yapan provider mı? False olanlar (arxiv, github, x_*,
    # meta_*) fast-race modunda yarış dışı kalır: genel sorgularda yarışı
    # kazanıp alakasız sonuç dönmeleri engellenir.
    general_web: bool = True

    def __init__(self, settings: Settings, http: Http):
        self.settings = settings
        self.http = http

    def available(self) -> bool:
        return True

    @abstractmethod
    async def search(
        self, query: str, max_results: int, recency: str | None
    ) -> list[ProviderResult]:
        raise NotImplementedError
