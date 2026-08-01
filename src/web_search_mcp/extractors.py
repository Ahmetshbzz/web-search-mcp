import io
import json
import re
from typing import Literal

import html2text
import pypdf
import trafilatura


def clean_extract(html: str) -> str:
    """Sayfanın ana içeriğini temiz metne çıkarır (trafilatura → lxml → regex fallback)."""
    try:
        text = trafilatura.extract(
            html, include_comments=False, include_tables=True, favor_precision=True
        )
        if text and text.strip():
            return re.sub(r"\n{3,}", "\n\n", text).strip()
    except Exception:
        pass
    try:
        from lxml import html as lxml_html

        text = lxml_html.fromstring(html).text_content()
    except Exception:
        text = re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", text).strip()


def clean_extract_markdown(html: str) -> str:
    """HTML'i başlıklar, tablolar ve kod bloklarını koruyarak Markdown formatına dönüştürür."""
    try:
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.ignore_images = True
        h.ignore_emphasis = False
        h.body_width = 0
        md = h.handle(html)
        if md and md.strip():
            return re.sub(r"\n{3,}", "\n\n", md).strip()
    except Exception:
        pass
    return clean_extract(html)


def extract_pdf(data_bytes: bytes) -> str:
    """PDF baytlarından metin çıkarır."""
    try:
        reader = pypdf.PdfReader(io.BytesIO(data_bytes))
        pages_text: list[str] = []
        for page in reader.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())
        return "\n\n".join(pages_text)
    except Exception:
        return ""


def extract_with_meta(
    html: str, url: str = "", output_format: Literal["text", "markdown"] = "text"
) -> tuple[str, str]:
    """(temiz ana içerik, yayın tarihi 'YYYY-MM-DD' veya '')."""
    date = ""
    try:
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
            date = (data.get("date") or "").strip()
    except Exception:
        pass

    text = clean_extract_markdown(html) if output_format == "markdown" else clean_extract(html)
    return text, date


def chunk_relevant_text(text: str, query: str, max_chars: int) -> str:
    """Metni paragraflara bölüp sorgu kelimelerine göre skorlar ve en alakalı kısımları döndürür."""
    if len(text) <= max_chars or not query.strip():
        return text[:max_chars]

    query_words = set(re.findall(r"\w+", query.lower()))
    if not query_words:
        return text[:max_chars]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text[:max_chars]

    scored_paragraphs: list[tuple[float, int, str]] = []
    for idx, p in enumerate(paragraphs):
        p_words = set(re.findall(r"\w+", p.lower()))
        overlap = len(query_words.intersection(p_words))
        score = overlap / (len(p_words) ** 0.1 + 1.0)
        scored_paragraphs.append((score, idx, p))

    # En yüksek skorluları seç, ancak orijinal sırasını koru
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
    selected: list[tuple[int, str]] = []
    current_length = 0

    for _score, idx, p in scored_paragraphs:
        if current_length + len(p) + 2 > max_chars and selected:
            break
        selected.append((idx, p))
        current_length += len(p) + 2

    selected.sort(key=lambda x: x[0])
    return "\n\n".join([p for _, p in selected])
