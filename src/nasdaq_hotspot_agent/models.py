from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class UniverseMember:
    ticker: str
    company: str
    theme_tags: list[str]
    is_core: bool = False


@dataclass(frozen=True)
class EtfMember:
    ticker: str
    name: str
    theme_tags: list[str]


@dataclass(frozen=True)
class StockSnapshot:
    ticker: str
    company: str
    index_weight_pct: float
    price_change_pct: float
    volume_ratio: float
    news_count: int
    catalysts: list[str]
    theme_tags: list[str]
    is_core: bool = False


@dataclass(frozen=True)
class EtfSnapshot:
    ticker: str
    name: str
    price_change_pct: float
    volume_ratio: float
    theme_tags: list[str]


@dataclass(frozen=True)
class NewsArticle:
    provider: str
    title: str
    summary: str
    url: str
    source: str
    published_at: datetime | None
    symbols: list[str]
    topics: list[str] = field(default_factory=list)
    sentiment: float | None = None
    source_type: str = "news"
    confidence: str = "medium"
    full_text_available: bool = False


@dataclass(frozen=True)
class MarketSnapshot:
    as_of: datetime
    index_changes: dict[str, float]
    stocks: list[StockSnapshot]
    etfs: list[EtfSnapshot]
    macro_notes: list[str] = field(default_factory=list)
    news_items: list[NewsArticle] = field(default_factory=list)
    provider_notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class StockScore:
    ticker: str
    company: str
    score: float
    index_weight_pct: float
    price_change_pct: float
    volume_ratio: float
    news_count: int
    catalysts: list[str]
    theme_tags: list[str]
    is_core: bool


@dataclass(frozen=True)
class ThemeSummary:
    name: str
    description: str
    score: float
    related_stocks: list[StockScore]
    related_etfs: list[EtfMember]
    catalysts: list[str]
    heat_level: str
