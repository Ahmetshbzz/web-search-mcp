import asyncio

import httpx

from web_search_mcp.config import Settings


class Http:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                follow_redirects=True,
                headers={
                    "User-Agent": self.settings.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                },
            )
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def get_text(self, url: str, request_timeout: float) -> str | None:
        try:
            resp = await self.client.get(url, timeout=request_timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception:  # noqa: BLE001 — best-effort.
            pass
        return None

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        request_timeout: float,
        json_body: dict[str, object] | None = None,
    ) -> object:
        last_error: Exception | None = None
        for attempt in range(self.settings.max_retries):
            try:
                if json_body is not None:
                    resp = await self.client.post(
                        url, json=json_body, headers=headers, timeout=request_timeout
                    )
                else:
                    resp = await self.client.get(
                        url, params=params, headers=headers, timeout=request_timeout
                    )
                resp.raise_for_status()
                return resp.json()
            except Exception as exc:  # noqa: BLE001 — provider hatası fallback tetikler.
                last_error = exc
                if attempt + 1 < self.settings.max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise last_error
