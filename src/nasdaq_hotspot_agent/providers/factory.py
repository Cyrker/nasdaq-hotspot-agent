from __future__ import annotations

from .base import MarketDataProvider
from .enriched import NewsEnrichedMarketDataProvider
from .mock import MockMarketDataProvider
from .stooq import StooqMarketDataProvider


def create_market_data_provider(name: str) -> MarketDataProvider:
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockMarketDataProvider()
    if normalized in {"mock_with_news", "enriched"}:
        return NewsEnrichedMarketDataProvider(MockMarketDataProvider())
    if normalized == "stooq":
        return StooqMarketDataProvider(MockMarketDataProvider())
    if normalized in {"news", "stooq_news"}:
        return NewsEnrichedMarketDataProvider(
            StooqMarketDataProvider(MockMarketDataProvider())
        )
    raise ValueError(f"Unsupported market data provider: {name}")
