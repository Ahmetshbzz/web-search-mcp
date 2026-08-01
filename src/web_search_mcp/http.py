import asyncio
from typing import Any

import httpx
from curl_cffi import requests as curl_requests

from web_search_mcp.config import Settings
from web_search_mcp.observability import get_logger

_logger = get_logger("http")


class Http:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: httpx.AsyncClient | None = None
        self._curl_session: curl_requests.AsyncSession | None = None

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

    @property
    def curl_session(self) -> curl_requests.AsyncSession:
        if self._curl_session is None:
            self._curl_session = curl_requests.AsyncSession(
                impersonate="chrome120",
                allow_redirects=True,
                headers={
                    "User-Agent": self.settings.user_agent,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
                },
            )
        return self._curl_session

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None
        if self._curl_session is not None:
            await self._curl_session.close()
        self._curl_session = None

    async def get_text(
        self, url: str, request_timeout: float, headers: dict[str, str] | None = None
    ) -> str | None:
        # First try curl_cffi with Chrome TLS impersonation to bypass Cloudflare/WAF
        try:
            resp = await self.curl_session.get(url, headers=headers, timeout=request_timeout)
            if resp.status_code == 200 and resp.text:
                return resp.text
        except Exception:
            _logger.debug("curl_cffi fetch failed, falling back to httpx for url %s", url)

        # Fallback to httpx
        try:
            resp = await self.client.get(url, headers=headers, timeout=request_timeout)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

    async def get_bytes(
        self, url: str, request_timeout: float, headers: dict[str, str] | None = None
    ) -> bytes | None:
        try:
            resp = await self.curl_session.get(url, headers=headers, timeout=request_timeout)
            if resp.status_code == 200 and resp.content:
                return resp.content
        except Exception:
            pass
        try:
            resp = await self.client.get(url, headers=headers, timeout=request_timeout)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    async def post_json(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        json_data: dict[str, object] | None = None,
        request_timeout: float,
    ) -> Any:
        return await self.get_json(
            url, headers=headers, json_body=json_data, request_timeout=request_timeout
        )

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
        request_timeout: float,
        json_body: dict[str, object] | None = None,
    ) -> Any:
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
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.settings.max_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
        assert last_error is not None
        raise last_error
