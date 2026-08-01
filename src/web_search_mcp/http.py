import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
from curl_cffi import requests as curl_requests

from web_search_mcp.config import Settings
from web_search_mcp.observability import get_logger

_logger = get_logger("http")

# Metin olarak decode edilebilecek content-type parçacıkları
_TEXTUAL_CT = ("text/", "json", "xml", "html", "markdown", "javascript", "x-www-form-urlencoded")

# Markdown-first: destekleyen sunucular (Cloudflare Markdown for Agents vb.)
# ham markdown döndürür → extraction atlanır, ciddi token tasarrufu.
_DOC_ACCEPT = "text/markdown, text/html, application/xhtml+xml, */*;q=0.8"


@dataclass
class DocumentResult:
    """get_document sonucu: içerik + yönlendirme sonrası final URL + tip bilgisi."""

    content: str | bytes | None
    final_url: str = ""
    content_type: str = ""
    status_code: int = 0
    too_large: bool = False


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

    @staticmethod
    def _decode_document(raw: bytes, content_type: str) -> str | bytes:
        ct = content_type.lower()
        if any(s in ct for s in _TEXTUAL_CT):
            return raw.decode("utf-8", errors="replace")
        return raw

    async def get_document(
        self,
        url: str,
        request_timeout: float,
        max_bytes: int = 10 * 1024 * 1024,
        headers: dict[str, str] | None = None,
    ) -> DocumentResult | None:
        """Streaming doküman indirme: boyut sınırı, final URL ve content-type döner.

        None → ağ hatası / 200 dışı durum (iki istemci de başarısız).
        too_large=True → içerik max_bytes'i aştı, indirme erken kesildi.
        """
        doc = await self._get_document_curl(url, request_timeout, max_bytes, headers)
        if doc is not None:
            return doc
        return await self._get_document_httpx(url, request_timeout, max_bytes, headers)

    async def _get_document_curl(
        self,
        url: str,
        request_timeout: float,
        max_bytes: int,
        headers: dict[str, str] | None,
    ) -> DocumentResult | None:
        try:
            hdrs = {"Accept": _DOC_ACCEPT, **(headers or {})}
            resp = await self.curl_session.get(
                url, headers=hdrs, timeout=request_timeout, stream=True
            )
            try:
                if resp.status_code != 200:
                    return None
                content_type = resp.headers.get("content-type", "")
                final_url = str(resp.url)
                declared = int(resp.headers.get("content-length") or 0)
                if declared > max_bytes:
                    return DocumentResult(
                        content=None,
                        final_url=final_url,
                        content_type=content_type,
                        status_code=resp.status_code,
                        too_large=True,
                    )
                chunks: list[bytes] = []
                total = 0
                too_large = False
                async for chunk in resp.aiter_content():
                    total += len(chunk)
                    if total > max_bytes:
                        too_large = True
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
                return DocumentResult(
                    content=None if too_large else self._decode_document(raw, content_type),
                    final_url=final_url,
                    content_type=content_type,
                    status_code=resp.status_code,
                    too_large=too_large,
                )
            finally:
                await resp.aclose()
        except Exception:
            _logger.debug("curl_cffi document fetch failed for url %s", url)
            return None

    async def _get_document_httpx(
        self,
        url: str,
        request_timeout: float,
        max_bytes: int,
        headers: dict[str, str] | None,
    ) -> DocumentResult | None:
        try:
            hdrs = {"Accept": _DOC_ACCEPT, **(headers or {})}
            async with self.client.stream(
                "GET", url, headers=hdrs, timeout=request_timeout
            ) as resp:
                if resp.status_code != 200:
                    return None
                content_type = resp.headers.get("content-type", "")
                final_url = str(resp.url)
                declared = int(resp.headers.get("content-length") or 0)
                if declared > max_bytes:
                    return DocumentResult(
                        content=None,
                        final_url=final_url,
                        content_type=content_type,
                        status_code=resp.status_code,
                        too_large=True,
                    )
                chunks: list[bytes] = []
                total = 0
                too_large = False
                async for chunk in resp.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        too_large = True
                        break
                    chunks.append(chunk)
                raw = b"".join(chunks)
                return DocumentResult(
                    content=None if too_large else self._decode_document(raw, content_type),
                    final_url=final_url,
                    content_type=content_type,
                    status_code=resp.status_code,
                    too_large=too_large,
                )
        except Exception:
            _logger.debug("httpx document fetch failed for url %s", url)
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
