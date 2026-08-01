import asyncio
from typing import Any, Literal

from web_search_mcp.extractors import clean_extract_markdown, extract_contacts_and_socials
from web_search_mcp.observability import get_logger

_logger = get_logger("browser_render")


class BrowserRenderEngine:
    def __init__(self) -> None:
        pass

    async def render_page(
        self,
        url: str,
        wait_until: Literal["load", "domcontentloaded", "networkidle"] = "networkidle",
        capture_network: bool = True,
        extract_shadow_dom: bool = True,
        render_timeout: float = 15000.0,
    ) -> dict[str, Any]:
        """Headless Chromium ile JavaScript derleyerek Shadow DOM ve Network JSON yakalar."""
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        _logger.info("Starting browser render for URL: %s", url)

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"error": "Playwright library is not installed.", "status": "error"}

        captured_requests: list[dict[str, Any]] = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()

                # Intercept XHR / Fetch JSON responses
                if capture_network:

                    async def handle_response(response: Any) -> None:
                        try:
                            req = response.request
                            resource_type = req.resource_type
                            if resource_type in ("fetch", "xhr") and response.status == 200:
                                content_type = response.headers.get("content-type", "")
                                if "json" in content_type:
                                    json_body = await response.json()
                                    captured_requests.append(
                                        {
                                            "url": response.url,
                                            "method": req.method,
                                            "status": response.status,
                                            "json_data": json_body,
                                        }
                                    )
                        except Exception:
                            pass

                    page.on("response", handle_response)

                await page.goto(url, wait_until=wait_until, timeout=render_timeout)
                await asyncio.sleep(1.0)  # Short stabilization wait

                full_html = await page.content()

                # Recursive Shadow DOM text extraction JS script
                if extract_shadow_dom:
                    shadow_js = (
                        "() => {"
                        "  function getDeepText(node) {"
                        "    let text = '';"
                        "    if (node.nodeType === Node.TEXT_NODE) {"
                        "      return node.textContent ? node.textContent.trim() : '';"
                        "    }"
                        "    if (node.shadowRoot) {"
                        "      for (let child of node.shadowRoot.childNodes) {"
                        "        text += ' ' + getDeepText(child);"
                        "      }"
                        "    }"
                        "    if (node.childNodes) {"
                        "      for (let child of node.childNodes) {"
                        "        text += ' ' + getDeepText(child);"
                        "      }"
                        "    }"
                        "    return text;"
                        "  }"
                        "  return getDeepText(document.body);"
                        "}"
                    )
                    text_content = await page.evaluate(shadow_js)
                else:
                    text_content = await page.evaluate("document.body.innerText")

                markdown_content = clean_extract_markdown(full_html)
                contacts = extract_contacts_and_socials(full_html)

                await browser.close()

                return {
                    "url": url,
                    "status": "ok",
                    "rendered_text": (text_content or "").strip()[:50000],
                    "markdown": markdown_content[:50000],
                    "contacts_found": contacts,
                    "captured_api_requests": captured_requests[:10],
                }

        except Exception as e:
            _logger.error("Browser render failed for %s: %s", url, str(e))
            return {"url": url, "status": "error", "error": str(e)}
