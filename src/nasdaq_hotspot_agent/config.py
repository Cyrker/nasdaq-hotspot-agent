from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .models import EtfMember, UniverseMember


@dataclass(frozen=True)
class ThemeConfig:
    name: str
    description: str
    etfs: list[str]


@dataclass(frozen=True)
class AiConfig:
    enabled: bool = False
    provider: str = "openai_compatible"
    model: str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout_seconds: int = 60
    report_language: str = "zh-CN"


@dataclass(frozen=True)
class MarketauxConfig:
    enabled: bool = False
    api_key_env: str = "MARKETAUX_API_KEY"
    api_key: str = ""
    symbol_batch_size: int = 8
    articles_per_request: int = 3


@dataclass(frozen=True)
class AlphaVantageNewsConfig:
    enabled: bool = False
    api_key_env: str = "ALPHA_VANTAGE_API_KEY"
    api_key: str = ""
    ticker_batch_size: int = 6
    limit_per_request: int = 20
    topics: list[str] | None = None


@dataclass(frozen=True)
class NasdaqRssConfig:
    enabled: bool = True
    feed_urls: list[str] | None = None
    symbol_feed_limit: int = 0


@dataclass(frozen=True)
class SecEdgarConfig:
    enabled: bool = True
    forms: list[str] | None = None
    max_symbols: int = 12
    user_agent: str = "nasdaq-hotspot-agent/0.1 contact@example.com"


@dataclass(frozen=True)
class StooqConfig:
    api_key_env: str = "STOOQ_API_KEY"
    api_key: str = ""
    timeout_seconds: int = 8


@dataclass(frozen=True)
class MarketDataConfig:
    stooq: StooqConfig = field(default_factory=StooqConfig)


@dataclass(frozen=True)
class NewsConfig:
    enabled: bool = True
    lookback_hours: int = 36
    max_articles_per_run: int = 40
    include_urls: bool = True
    request_timeout_seconds: int = 12
    marketaux: MarketauxConfig = field(default_factory=MarketauxConfig)
    alpha_vantage: AlphaVantageNewsConfig = field(default_factory=AlphaVantageNewsConfig)
    nasdaq_rss: NasdaqRssConfig = field(default_factory=NasdaqRssConfig)
    sec_edgar: SecEdgarConfig = field(default_factory=SecEdgarConfig)


@dataclass(frozen=True)
class AgentConfig:
    title: str
    timezone: str
    max_themes: int
    max_stocks_per_theme: int
    score_weights: dict[str, float]
    universe: list[UniverseMember]
    etfs: list[EtfMember]
    themes: dict[str, ThemeConfig]
    ai: AiConfig
    market_data: MarketDataConfig
    news: NewsConfig


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_list(value: object, default: list[str] | None = None) -> list[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        raw_items = (
            value.replace("，", "\n")
            .replace(",", "\n")
            .replace(";", "\n")
            .replace("；", "\n")
            .splitlines()
        )
    elif isinstance(value, (list, tuple, set)):
        raw_items = value
    else:
        raw_items = []
    items: list[str] = []
    seen: set[str] = set()
    for raw_item in raw_items:
        item = str(raw_item or "").strip()
        if item and item not in seen:
            items.append(item)
            seen.add(item)
    return items


def load_config(path: str | Path) -> AgentConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    report = data["report"]
    ai_data = data.get("ai", {})
    news_data = data.get("news", {})
    market_data = data.get("market_data", {})
    stooq_data = market_data.get("stooq", {})
    marketaux_data = news_data.get("marketaux", {})
    alpha_data = news_data.get("alpha_vantage", {})
    nasdaq_data = news_data.get("nasdaq_rss", {})
    sec_data = news_data.get("sec_edgar", {})

    core = [
        UniverseMember(
            ticker=item["ticker"],
            company=item["company"],
            theme_tags=list(item["theme_tags"]),
            is_core=True,
        )
        for item in data["core_universe"]
    ]
    extended = [
        UniverseMember(
            ticker=item["ticker"],
            company=item["company"],
            theme_tags=list(item["theme_tags"]),
            is_core=False,
        )
        for item in data["extended_universe"]
    ]
    etfs = [
        EtfMember(
            ticker=item["ticker"],
            name=item["name"],
            theme_tags=list(item["theme_tags"]),
        )
        for item in data["etfs"]
    ]
    themes = {
        name: ThemeConfig(
            name=name,
            description=item["description"],
            etfs=list(item.get("etfs", [])),
        )
        for name, item in data["themes"].items()
    }

    return AgentConfig(
        title=report["title"],
        timezone=report["timezone"],
        max_themes=_as_int(report.get("max_themes"), 6),
        max_stocks_per_theme=_as_int(report.get("max_stocks_per_theme"), 8),
        score_weights=dict(data["score_weights"]),
        universe=core + extended,
        etfs=etfs,
        themes=themes,
        ai=AiConfig(
            enabled=_as_bool(ai_data.get("enabled"), False),
            provider=str(ai_data.get("provider", "openai_compatible")),
            model=str(ai_data.get("model", "gpt-4.1-mini")),
            base_url=str(ai_data.get("base_url", "https://api.openai.com/v1")),
            api_key_env=str(ai_data.get("api_key_env", "OPENAI_API_KEY")),
            api_key=str(ai_data.get("api_key", "")),
            temperature=_as_float(ai_data.get("temperature"), 0.2),
            max_tokens=_as_int(ai_data.get("max_tokens"), 1200),
            timeout_seconds=_as_int(ai_data.get("timeout_seconds"), 60),
            report_language=str(ai_data.get("report_language", "zh-CN")),
        ),
        market_data=MarketDataConfig(
            stooq=StooqConfig(
                api_key_env=str(stooq_data.get("api_key_env", "STOOQ_API_KEY")),
                api_key=str(stooq_data.get("api_key", "")),
                timeout_seconds=_as_int(stooq_data.get("timeout_seconds"), 8),
            )
        ),
        news=NewsConfig(
            enabled=_as_bool(news_data.get("enabled"), True),
            lookback_hours=_as_int(news_data.get("lookback_hours"), 36),
            max_articles_per_run=_as_int(news_data.get("max_articles_per_run"), 40),
            include_urls=_as_bool(news_data.get("include_urls"), True),
            request_timeout_seconds=_as_int(
                news_data.get("request_timeout_seconds"), 12
            ),
            marketaux=MarketauxConfig(
                enabled=_as_bool(marketaux_data.get("enabled"), False),
                api_key_env=str(marketaux_data.get("api_key_env", "MARKETAUX_API_KEY")),
                api_key=str(marketaux_data.get("api_key", "")),
                symbol_batch_size=_as_int(marketaux_data.get("symbol_batch_size"), 8),
                articles_per_request=_as_int(
                    marketaux_data.get("articles_per_request"), 3
                ),
            ),
            alpha_vantage=AlphaVantageNewsConfig(
                enabled=_as_bool(alpha_data.get("enabled"), False),
                api_key_env=str(alpha_data.get("api_key_env", "ALPHA_VANTAGE_API_KEY")),
                api_key=str(alpha_data.get("api_key", "")),
                ticker_batch_size=_as_int(alpha_data.get("ticker_batch_size"), 6),
                limit_per_request=_as_int(alpha_data.get("limit_per_request"), 20),
                topics=_as_list(
                    alpha_data.get("topics"),
                    ["technology", "earnings", "financial_markets"],
                ),
            ),
            nasdaq_rss=NasdaqRssConfig(
                enabled=_as_bool(nasdaq_data.get("enabled"), True),
                feed_urls=_as_list(
                    nasdaq_data.get("feed_urls"),
                    [
                        "https://www.nasdaq.com/feed/rssoutbound?category=Artificial+Intelligence",
                        "https://www.nasdaq.com/feed/rssoutbound?category=Technology",
                        "https://www.nasdaq.com/feed/rssoutbound?category=Stocks",
                        "https://www.nasdaq.com/feed/rssoutbound?category=Earnings",
                    ],
                ),
                symbol_feed_limit=_as_int(nasdaq_data.get("symbol_feed_limit"), 0),
            ),
            sec_edgar=SecEdgarConfig(
                enabled=_as_bool(sec_data.get("enabled"), True),
                forms=_as_list(sec_data.get("forms"), ["8-K", "10-Q", "10-K", "S-1"]),
                max_symbols=_as_int(sec_data.get("max_symbols"), 12),
                user_agent=str(
                    sec_data.get(
                        "user_agent",
                        "nasdaq-hotspot-agent/0.1 contact@example.com",
                    )
                ),
            ),
        ),
    )
