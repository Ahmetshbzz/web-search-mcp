from web_search_mcp.text import truncate


def test_truncate_short_text():
    assert truncate("kisa", 100) == "kisa"


def test_truncate_cuts_at_word_boundary():
    result = truncate("bir kelime iki kelime uc kelime dort", 14)
    assert result.endswith("…")
    assert result == "bir kelime…"


def test_truncate_empty():
    assert truncate("", 10) == ""


def test_truncate_long_single_word():
    result = truncate("x" * 50, 10)
    assert result.startswith("x" * 10)
    assert result.endswith("…")
