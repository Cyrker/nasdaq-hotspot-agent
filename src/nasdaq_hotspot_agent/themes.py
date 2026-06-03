from __future__ import annotations

from .config import AgentConfig
from .models import EtfMember, StockScore, ThemeSummary
from .scoring import heat_level


def summarize_themes(config: AgentConfig, stocks: list[StockScore]) -> list[ThemeSummary]:
    stocks_by_theme: dict[str, list[StockScore]] = {}
    for stock in stocks:
        for theme in stock.theme_tags:
            if theme in config.themes:
                stocks_by_theme.setdefault(theme, []).append(stock)

    etfs_by_ticker = {etf.ticker: etf for etf in config.etfs}
    summaries: list[ThemeSummary] = []

    for theme_name, related in stocks_by_theme.items():
        theme_config = config.themes[theme_name]
        top_stocks = sorted(related, key=lambda item: item.score, reverse=True)[
            : config.max_stocks_per_theme
        ]
        if not top_stocks:
            continue

        theme_score = round(
            sum(stock.score for stock in top_stocks) / len(top_stocks)
            + min(len(top_stocks), 5) * 2,
            1,
        )
        catalysts = collect_catalysts(top_stocks)
        etfs = [
            etfs_by_ticker[ticker]
            for ticker in theme_config.etfs
            if ticker in etfs_by_ticker
        ]
        summaries.append(
            ThemeSummary(
                name=theme_name,
                description=theme_config.description,
                score=theme_score,
                related_stocks=top_stocks,
                related_etfs=etfs,
                catalysts=catalysts,
                heat_level=heat_level(theme_score),
            )
        )

    return sorted(summaries, key=lambda item: item.score, reverse=True)[
        : config.max_themes
    ]


def collect_catalysts(stocks: list[StockScore]) -> list[str]:
    seen: set[str] = set()
    catalysts: list[str] = []
    for stock in stocks:
        for item in stock.catalysts:
            if item not in seen:
                seen.add(item)
                catalysts.append(item)
            if len(catalysts) >= 4:
                return catalysts
    return catalysts
