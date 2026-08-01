from datetime import date, timedelta

from web_search_mcp.dates import normalize_date


def test_absolute_date():
    assert normalize_date("Published 2024-03-05") == "2024-03-05"


def test_relative_days_ago():
    expected = (date.today() - timedelta(days=2)).isoformat()
    assert normalize_date("2 days ago") == expected


def test_relative_turkish():
    expected = (date.today() - timedelta(days=3)).isoformat()
    assert normalize_date("3 gün önce") == expected


def test_relative_words():
    assert normalize_date("yesterday") == (date.today() - timedelta(days=1)).isoformat()
    assert normalize_date("today") == date.today().isoformat()
    assert normalize_date("last week") == (date.today() - timedelta(days=7)).isoformat()


def test_relative_units():
    assert normalize_date("1 week ago") == (date.today() - timedelta(weeks=1)).isoformat()
    assert normalize_date("2 month ago") == (date.today() - timedelta(days=60)).isoformat()
    assert normalize_date("1 year ago") == (date.today() - timedelta(days=365)).isoformat()


def test_hours():
    assert normalize_date("5 hours ago") == (date.today() - timedelta(hours=5)).isoformat()


def test_unparseable():
    assert normalize_date("bogus string") == ""
    assert normalize_date("") == ""
