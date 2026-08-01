import json
import re


def clean_extract(html: str) -> str:
    """Sayfanın ana içeriğini temiz metne çıkarır (trafilatura → lxml → regex fallback)."""
    try:
        import trafilatura

        text = trafilatura.extract(
            html, include_comments=False, include_tables=True, favor_precision=True
        )
        if text and text.strip():
            return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:  # noqa: BLE001
        pass
    try:
        from lxml import html as lxml_html

        text = lxml_html.fromstring(html).text_content()
    except Exception:  # noqa: BLE001
        text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def extract_with_meta(html: str, url: str = "") -> tuple[str, str]:
    """(temiz ana metin, yayın tarihi 'YYYY-MM-DD' veya ''). trafilatura metadata ile tarih."""
    try:
        import trafilatura

        raw = trafilatura.extract(
            html,
            url=url or None,
            output_format="json",
            with_metadata=True,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        if raw:
            data = json.loads(raw)
            text = (data.get("text") or "").strip()
            if text:
                date = (data.get("date") or "").strip()
                return re.sub(r"\n{3,}", "\n\n", text), date
    except Exception:  # noqa: BLE001
        pass
    return clean_extract(html), ""
