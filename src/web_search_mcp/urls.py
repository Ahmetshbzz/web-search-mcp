import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_PRIVATE_HOST_RE = re.compile(
    r"^(localhost|127\.|10\.|192\.168\.|169\.254\.|172\.(1[6-9]|2\d|3[01])\.|::1$|0\.0\.0\.0)"
)

_TRACKING_PARAMS = frozenset(
    {
        "fbclid", "gclid", "dclid", "gbraid", "wbraid", "msclkid", "twclid",
        "yclid", "igshid", "li_fat_id", "_ga", "_gl", "_hsenc", "_hsmi",
        "mc_cid", "mc_eid", "ref_src", "ref_url", "srsltid", "source",
        "spm", "si", "scid", "cmpid", "share_token", "utm_*",
    }
)


def hostname(url: str) -> str:
    host = urlparse(url).hostname or url
    return host[4:] if host.startswith("www.") else host


def is_fetchable(url: str) -> bool:
    parsed = urlparse(url)
    return bool(
        parsed.scheme in ("http", "https")
        and parsed.hostname
        and not _PRIVATE_HOST_RE.match(parsed.hostname)
    )


def clean_url(url: str) -> str:
    """Tracking sorgu parametrelerini düşürür; URL tanınmazsa olduğu gibi döner."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return url
    keep = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k not in _TRACKING_PARAMS and not k.startswith(("utm_", "pk_", "piwik_"))
    ]
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(keep), parsed.fragment)
    )


def authority_score(host: str) -> int:
    """Generic otorite proxy: gov/edu en güçlü; docs/developer/api subdomain'i + .org orta."""
    h = (host or "").lower()
    score = 0
    if h.endswith((".gov", ".edu")) or ".gov." in h or ".edu." in h:
        score += 3
    if h.split(".")[0] in ("docs", "developer", "dev", "api", "wiki"):
        score += 2
    if h.endswith(".org"):
        score += 1
    return score
