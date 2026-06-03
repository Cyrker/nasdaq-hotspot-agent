from __future__ import annotations

from .base import MarketDataProvider
from .enriched import NewsEnrichedMarketDataProvider
from .mock import MockMarketDataProvider


def create_market_data_provider(name: str) -> MarketDataProvider:
    normalized = name.strip().lower()
    if normalized == "mock":
        return MockMarketDataProvider()
    if normalized in {"news", "mock_with_news", "enriched"}:
        return NewsEnrichedMarketDataProvider(MockMarketDataProvider())
    raise ValueError(f"Unsupported market data provider: {name}")
