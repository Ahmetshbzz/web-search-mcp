from typing import Literal

from pydantic import BaseModel


class ProviderResult(BaseModel):
    title: str = ""
    href: str = ""
    body: str = ""
    date: str = ""


class EnrichedResult(BaseModel):
    title: str = ""
    href: str = ""
    snippet: str = ""
    content: str = ""
    date: str = ""


class SearchHit(BaseModel):
    title: str
    href: str
    body: str
    label: str = ""


class FetchPage(BaseModel):
    status: Literal["ok", "unreachable", "empty", "blocked", "too_large", "binary"]
    text: str = ""
    date: str = ""
    final_url: str = ""  # yönlendirme sonrası ulaşılan gerçek URL
