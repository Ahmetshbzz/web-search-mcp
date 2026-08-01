def truncate(text: str, limit: int) -> str:
    """Metni whitespace sınırından keser; kelime ortasından kırpmaz."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    cut = cut.rsplit("\n", 1)[0]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip() + "…"
