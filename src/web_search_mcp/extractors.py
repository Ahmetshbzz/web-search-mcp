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


def extract_contacts_and_socials(html: str) -> dict[str, list[str]]:
    """HTML içerisinden WhatsApp, telefon, e-posta ve sosyal medya bağlantılarını çıkarır."""
    if not html:
        return {}

    contacts: dict[str, list[str]] = {
        "whatsapp": [],
        "phone": [],
        "email": [],
        "telegram": [],
        "socials": [],
    }

    # WhatsApp links/numbers
    wa_matches = re.findall(
        r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp://send\?phone=)(\+?\d+)",
        html,
        re.IGNORECASE,
    )
    for num in wa_matches:
        formatted = "+" + num.lstrip("+")
        if formatted not in contacts["whatsapp"]:
            contacts["whatsapp"].append(formatted)

    # Tel hrefs
    tel_matches = re.findall(r'href=["\']tel:([^"\']+)["\']', html, re.IGNORECASE)
    for tel in tel_matches:
        t_clean = re.sub(r"[^\d+]", "", tel)
        if t_clean and t_clean not in contacts["phone"]:
            contacts["phone"].append(t_clean)

    # Mailto hrefs
    mail_matches = re.findall(r'href=["\']mailto:([^"\']+)["\']', html, re.IGNORECASE)
    for mail in mail_matches:
        m_clean = mail.split("?")[0].strip()
        if m_clean and m_clean not in contacts["email"]:
            contacts["email"].append(m_clean)

    # Telegram
    tg_matches = re.findall(
        r'href=["\'](https?://(?:t|telegram)\.me/[^"\']+)["\']', html, re.IGNORECASE
    )
    for tg in tg_matches:
        if tg not in contacts["telegram"]:
            contacts["telegram"].append(tg)

    # Socials
    social_patterns = [
        r'href=["\'](https?://(?:www\.)?github\.com/[^"\']+)["\']',
        r'href=["\'](https?://(?:www\.)?linkedin\.com/in/[^"\']+)["\']',
        r'href=["\'](https?://(?:www\.)?(?:twitter|x)\.com/[^"\']+)["\']',
        r'href=["\'](https?://(?:www\.)?instagram\.com/[^"\']+)["\']',
    ]
    for pattern in social_patterns:
        for match in re.findall(pattern, html, re.IGNORECASE):
            if match not in contacts["socials"]:
                contacts["socials"].append(match)

    return {k: v for k, v in contacts.items() if v}


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

    # Append discovered contact and action links (WhatsApp, Phone, Email, Telegram, Socials)
    contacts = extract_contacts_and_socials(html)
    if contacts:
        contact_lines = ["\n\n### Discovered Contacts & Action Links:"]
        if "whatsapp" in contacts:
            contact_lines.append(f"- **WhatsApp:** {', '.join(contacts['whatsapp'])}")
        if "phone" in contacts:
            contact_lines.append(f"- **Phone:** {', '.join(contacts['phone'])}")
        if "email" in contacts:
            contact_lines.append(f"- **Email:** {', '.join(contacts['email'])}")
        if "telegram" in contacts:
            contact_lines.append(f"- **Telegram:** {', '.join(contacts['telegram'])}")
        if "socials" in contacts:
            contact_lines.append(f"- **Socials:** {', '.join(contacts['socials'])}")
        text += "\n".join(contact_lines)

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
