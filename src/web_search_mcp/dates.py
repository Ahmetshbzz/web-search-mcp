import re
from datetime import date, timedelta

_RELATIVE_RE = re.compile(
    r"(?i)(today|bugün|yesterday|dün|last week|geçen hafta|last month|geçen ay|last year|geçen yıl)"
    r"|(\d+)\s*(minutes?|dakika|hours?|saat|days?|gün|weeks?|hafta|months?|ay|years?|yıl)\s*(ago|önce)"
)


def normalize_date(value: str) -> str:
    """Karışık tarih string'ini YYYY-MM-DD'ye indirger; göreli ifadeleri de çözer (yoksa '')."""
    text = str(value or "").strip()
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        return match.group(0)
    rel = _RELATIVE_RE.search(text)
    if not rel:
        return ""
    today = date.today()
    if rel.group(1):
        word = rel.group(1).lower()
        if word in ("today", "bugün"):
            return today.isoformat()
        if word in ("yesterday", "dün"):
            return (today - timedelta(days=1)).isoformat()
        if word in ("last week", "geçen hafta"):
            return (today - timedelta(days=7)).isoformat()
        if word in ("last month", "geçen ay"):
            return (today - timedelta(days=30)).isoformat()
        if word in ("last year", "geçen yıl"):
            return (today - timedelta(days=365)).isoformat()
    n = int(rel.group(2))
    unit = rel.group(3).lower()
    if unit in ("day", "days", "gün"):
        return (today - timedelta(days=n)).isoformat()
    if unit in ("week", "weeks", "hafta"):
        return (today - timedelta(weeks=n)).isoformat()
    if unit in ("month", "months", "ay"):
        return (today - timedelta(days=30 * n)).isoformat()
    if unit in ("year", "years", "yıl"):
        return (today - timedelta(days=365 * n)).isoformat()
    if unit in ("hour", "hours", "saat"):
        return (today - timedelta(hours=n)).isoformat()
    if unit in ("minute", "minutes", "dakika"):
        return (today - timedelta(minutes=n)).isoformat()
    return ""
