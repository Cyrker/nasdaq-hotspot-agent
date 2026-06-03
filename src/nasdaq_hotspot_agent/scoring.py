from __future__ import annotations

from .models import MarketSnapshot, StockScore


def clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


def score_stocks(snapshot: MarketSnapshot, weights: dict[str, float]) -> list[StockScore]:
    theme_counts: dict[str, int] = {}
    for stock in snapshot.stocks:
        if abs(stock.price_change_pct) >= 1.0 or stock.news_count >= 3:
            for theme in stock.theme_tags:
                theme_counts[theme] = theme_counts.get(theme, 0) + 1

    scored = []
    for stock in snapshot.stocks:
        index_weight_score = clamp(stock.index_weight_pct / 9.0 * 100.0)
        price_move_score = clamp(abs(stock.price_change_pct) / 4.0 * 100.0)
        volume_signal_score = clamp((stock.volume_ratio - 1.0) / 1.0 * 100.0)
        news_density_score = clamp(stock.news_count / 8.0 * 100.0)
        theme_breadth_score = clamp(
            max(theme_counts.get(theme, 0) for theme in stock.theme_tags) / 5.0 * 100.0
            if stock.theme_tags
            else 0.0
        )

        score = (
            weights["index_weight"] * index_weight_score
            + weights["price_move"] * price_move_score
            + weights["volume_signal"] * volume_signal_score
            + weights["news_density"] * news_density_score
            + weights["theme_breadth"] * theme_breadth_score
        )

        scored.append(
            StockScore(
                ticker=stock.ticker,
                company=stock.company,
                score=round(score, 1),
                index_weight_pct=stock.index_weight_pct,
                price_change_pct=stock.price_change_pct,
                volume_ratio=stock.volume_ratio,
                news_count=stock.news_count,
                catalysts=stock.catalysts,
                theme_tags=stock.theme_tags,
                is_core=stock.is_core,
            )
        )

    return sorted(scored, key=lambda item: item.score, reverse=True)


def heat_level(score: float) -> str:
    if score >= 75:
        return "高"
    if score >= 55:
        return "中高"
    if score >= 35:
        return "中"
    return "低"
