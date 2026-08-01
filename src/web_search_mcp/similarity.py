"""Keyword-ötesi eşleştirme: char n-gram (subword) benzerliği + kısaltma genişletme.

Saf keyword/BM25 eşleştirmesi şunlarda kör kalır:
- Morfoloji: "kitap" ~ "kitaplarımda", "searching" ~ "search"
- Tire/alt-kelime: "nogil" ~ "no-GIL", "free-threading" ~ "freethread"
- Kısaltmalar: "GIL" ~ "global interpreter lock", "k8s" ~ "kubernetes"

Embedding modeli olmadan (sıfır yeni bağımlılık) bu iki heuristic ile
yakalanır: karakter trigram'ları subword sinyali verir, küçük bir
kısaltma sözlüğü de yaygın teknik eşdeğerleri ekler.
"""

import re

# Yaygın teknik kısaltma ↔ genişletme eşlemesi (arama sorguları için)
_ABBREVIATIONS: dict[str, str] = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "dl": "deep learning",
    "nlp": "natural language processing",
    "llm": "large language model",
    "rag": "retrieval augmented generation",
    "mcp": "model context protocol",
    "gil": "global interpreter lock",
    "k8s": "kubernetes",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "db": "database",
    "api": "application programming interface",
    "sdk": "software development kit",
    "cli": "command line interface",
    "ui": "user interface",
    "ux": "user experience",
    "sso": "single sign on",
    "rbac": "role based access control",
    "tls": "transport layer security",
    "ssl": "secure sockets layer",
    "dns": "domain name system",
    "vpn": "virtual private network",
    "cdn": "content delivery network",
    "ssr": "server side rendering",
    "ssg": "static site generation",
    "csr": "client side rendering",
    "spa": "single page application",
    "pwa": "progressive web app",
    "wasm": "webassembly",
    "gpu": "graphics processing unit",
    "cpu": "central processing unit",
    "iot": "internet of things",
    "oauth": "open authorization",
    "jwt": "json web token",
    "grpc": "google remote procedure call",
    "sql": "structured query language",
    "orm": "object relational mapping",
    "ci": "continuous integration",
    "cd": "continuous delivery",
}

# Genişletme → kısaltma ters eşlemesi ("kubernetes" sorgusuna "k8s" ekler)
_REVERSE_ABBREVIATIONS: dict[str, str] = {v: k for k, v in _ABBREVIATIONS.items()}


def expand_query_terms(query: str) -> set[str]:
    """Sorgu kelimeleri + kısaltma/genişletme eşdeğerleri."""
    words = set(re.findall(r"\w+", query.lower()))
    expanded = set(words)
    for w in list(words):
        if w in _ABBREVIATIONS:
            expanded.update(re.findall(r"\w+", _ABBREVIATIONS[w]))
        if w in _REVERSE_ABBREVIATIONS:
            expanded.add(_REVERSE_ABBREVIATIONS[w])
    return expanded


def char_ngrams(text: str, n: int = 3) -> set[str]:
    """Metnin karakter n-gram kümesi (subword birimleri)."""
    padded = f" {text.lower()} "
    if len(padded) <= n:
        return {padded}
    return {padded[i : i + n] for i in range(len(padded) - n + 1)}


def ngram_similarity(query: str, text: str, n: int = 3, max_scan: int = 6000) -> float:
    """Query n-gram'larının metin içindeki containment benzerliği (0..~).

    Morfoloji ve tire/birleşik yazım farklarına dayanıklıdır:
    "kitap" trigram'ları "kitaplarımda" içinde büyük ölçüde bulunur.
    """
    q = char_ngrams(query, n)
    if not q or not text.strip():
        return 0.0
    t = char_ngrams(text[:max_scan], n)
    if not t:
        return 0.0
    return len(q & t) / (len(q) ** 0.5)
