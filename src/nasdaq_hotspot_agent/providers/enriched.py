from __future__ import annotations

from dataclasses import replace

from ..config import AgentConfig
from ..models import MarketSnapshot, NewsArticle, StockSnapshot
from .base import MarketDataProvider
from .news import NewsAggregator


class NewsEnrichedMarketDataProvider(MarketDataProvider):
    def __init__(self, base_provider: MarketDataProvider) -> None:
        self.base_provider = base_provider
        self.news_aggregator = NewsAggregator()

    def fetch_snapshot(self, config: AgentConfig) -> MarketSnapshot:
        snapshot = self.base_provider.fetch_snapshot(config)
        result = self.news_aggregator.fetch(config)
        if not result.articles:
            return replace(
                snapshot,
                provider_notes=[*snapshot.provider_notes, *result.notes],
            )

        articles_by_symbol = self._group_articles_by_symbol(result.articles)
        stocks = [
            self._enrich_stock(stock, articles_by_symbol.get(stock.ticker, []))
            for stock in snapshot.stocks
        ]
        macro_notes = [
            *snapshot.macro_notes,
            "已接入真实新闻/公告线索；新闻 API 摘要只作为线索，SEC filing 作为高可信官方证据。",
        ]
        return replace(
            snapshot,
            stocks=stocks,
            macro_notes=macro_notes,
            news_items=result.articles,
            provider_notes=[*snapshot.provider_notes, *result.notes],
        )

    def _group_articles_by_symbol(
        self,
        articles: list[NewsArticle],
    ) -> dict[str, list[NewsArticle]]:
        grouped: dict[str, list[NewsArticle]] = {}
        for article in articles:
            for symbol in article.symbols:
                grouped.setdefault(symbol.upper(), []).append(article)
        return grouped

    def _enrich_stock(
        self,
        stock: StockSnapshot,
        articles: list[NewsArticle],
    ) -> StockSnapshot:
        if not articles:
            return stock

        catalysts: list[str] = []
        seen: set[str] = set()
        for article in articles[:5]:
            title = article.title.strip()
            if title and title not in seen:
                catalysts.append(title)
                seen.add(title)
        return replace(
            stock,
            news_count=max(stock.news_count, len(articles)),
            catalysts=catalysts or stock.catalysts,
        )
