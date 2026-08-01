import io
import json
import re
from typing import Literal

import html2text
import pypdf
import trafilatura

from web_search_mcp.similarity import char_ngrams, expand_query_terms, ngram_similarity


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


# Tek birleşik desen: HTML'i 9 kez taramak yerine tek geçişte tüm iletişim
# bağlantılarını yakalar. Grup adları kategori dispatch'i için kullanılır.
_CONTACT_RE = re.compile(
    r"(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp://send\?phone=)(?P<wa>\+?\d+)"
    r"|href=[\"']tel:(?P<tel>[^\"']+)[\"']"
    r"|href=[\"']mailto:(?P<mail>[^\"']+)[\"']"
    r"|href=[\"'](?P<tg>https?://(?:t|telegram)\.me/[^\"']+)[\"']"
    r"|href=[\"'](?P<social>https?://(?:www\.)?"
    r"(?:github\.com|linkedin\.com/in|(?:twitter|x)\.com|instagram\.com)/[^\"']+)[\"']",
    re.IGNORECASE,
)


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
    seen: dict[str, set[str]] = {k: set() for k in contacts}

    for match in _CONTACT_RE.finditer(html):
        kind = match.lastgroup
        if kind is None:
            continue
        value = match.group(kind)
        if kind == "wa":
            category, cleaned = "whatsapp", "+" + value.lstrip("+")
        elif kind == "tel":
            category, cleaned = "phone", re.sub(r"[^\d+]", "", value)
        elif kind == "mail":
            category, cleaned = "email", value.split("?")[0].strip()
        elif kind == "tg":
            category, cleaned = "telegram", value
        else:
            category, cleaned = "socials", value
        if cleaned and cleaned not in seen[category]:
            seen[category].add(cleaned)
            contacts[category].append(cleaned)

    return {k: v for k, v in contacts.items() if v}


def extract_with_meta(
    html: str, url: str = "", output_format: Literal["text", "markdown"] = "text"
) -> tuple[str, str]:
    """(temiz ana içerik, yayın tarihi 'YYYY-MM-DD' veya '').

    Tek trafilatura JSON çağrısından hem metin hem tarih alınır; text formatında
    ikinci bir trafilatura geçişi yapılmaz (lxml/regex fallback korunur).
    """
    date = ""
    json_text = ""
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
            json_text = (data.get("text") or "").strip()
    except Exception:
        pass

    if output_format == "markdown":
        text = clean_extract_markdown(html)
    elif json_text:
        text = re.sub(r"\n{3,}", "\n\n", json_text)
    else:
        text = clean_extract(html)

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


def _best_window(text: str, query: str, max_chars: int) -> str:
    """Dev metin içinde sorguyla en yüksek subword benzerliğine sahip pencereyi bulur.

    Kayar pencere + IDF ağırlıklı char n-gram taraması: dokümanda nadir geçen
    sorgu n-gram'ları yüksek ağırlık alır. Aksi halde "go1.26" gibi yaygın
    trigram'lar sayfanın her yerine yayılmışken spesifik bölgeyi ("go1.26.5")
    boğar ve pencere sayfa başına kayar (go.dev dogfood bulgusu).
    """
    if len(text) <= max_chars:
        return text

    # Orijinal sorgu metni korunur: "go1.26.5" gibi tek token'lar parçalanmaz.
    # Genişletme terimleri (kısaltma açılımları) ayrıca eklenir.
    raw_words = set(re.findall(r"\w+", query.lower()))
    q_ngrams = char_ngrams(query)
    for term in expand_query_terms(query) - raw_words:
        q_ngrams |= char_ngrams(term)
    if not q_ngrams:
        return text[:max_chars].rstrip()

    # Nadirlik ağırlığı: n-gram dokümanda ne kadar az geçiyorsa o kadar değerli
    lower_text = text.lower()
    weights = {g: 1.0 / (1.0 + lower_text.count(g)) for g in q_ngrams}

    step = max(1, max_chars // 4)
    best_score, best_start = -1.0, 0
    for start in range(0, len(text) - max_chars + 1, step):
        window_ngrams = char_ngrams(text[start : start + max_chars])
        score = sum(weights[g] for g in window_ngrams & q_ngrams)
        if score > best_score:
            best_score, best_start = score, start
    if best_score <= 0:
        return text[:max_chars].rstrip()

    # Pencereyi ilk kelime eşleşmesine yasla: sabit sınırlar eşleşmeyi ortadan
    # kesebilir ("2026-07-07"nin "2026-07"de kırpılması gibi). Kaydır + kenetle.
    window = text[best_start : best_start + max_chars].lower()
    positions = [p for w in raw_words if (p := window.find(w)) != -1]
    if positions:
        anchor = best_start + min(positions)
        start = max(0, anchor - max_chars // 4)
        if start + max_chars > len(text):
            start = max(0, len(text) - max_chars)
        return text[start : start + max_chars].rstrip()
    return text[best_start : best_start + max_chars].rstrip()


def chunk_relevant_text(text: str, query: str, max_chars: int) -> str:
    """Metni paragraflara bölüp sorguyla alakasına göre skorlar; en alakalı kısımları döndürür.

    Skor = kelime overlap (kısaltma genişletmeli) + subword n-gram benzerliği.
    """
    if len(text) <= max_chars or not query.strip():
        return text[:max_chars]

    query_words = expand_query_terms(query)
    if not query_words:
        return text[:max_chars]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if not paragraphs:
        return text[:max_chars]

    scored_paragraphs: list[tuple[float, int, str]] = []
    for idx, p in enumerate(paragraphs):
        p_words = set(re.findall(r"\w+", p.lower()))
        overlap = len(query_words.intersection(p_words))
        lex_score = overlap / (len(p_words) ** 0.1 + 1.0)
        sub_score = ngram_similarity(query, p)
        scored_paragraphs.append((lex_score + 0.5 * sub_score, idx, p))

    # En yüksek skorluları seç, ancak orijinal sırasını koru
    scored_paragraphs.sort(key=lambda x: x[0], reverse=True)
    selected: list[tuple[int, str]] = []
    current_length = 0

    for _score, idx, p in scored_paragraphs:
        remaining = max_chars - current_length
        if len(p) + 2 > remaining:
            if selected:
                break
            # Tek dev paragraf (trafilatura çıktısı tipik): sorgu bölgesini
            # pencereler, aksi halde max_chars hiç uygulanmaz → token kaçağı.
            return _best_window(p, query, remaining)
        selected.append((idx, p))
        current_length += len(p) + 2

    selected.sort(key=lambda x: x[0])
    return "\n\n".join([p for _, p in selected])
