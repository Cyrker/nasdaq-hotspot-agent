from __future__ import annotations

from dataclasses import dataclass

from .config import AgentConfig
from .models import MarketSnapshot, StockScore, ThemeSummary
from .providers.base import MarketDataProvider
from .report import generate_markdown_report
from .scoring import score_stocks
from .themes import summarize_themes


@dataclass(frozen=True)
class AgentRunResult:
    snapshot: MarketSnapshot
    stocks: list[StockScore]
    themes: list[ThemeSummary]
    markdown: str


class NasdaqHotspotAgent:
    def __init__(self, config: AgentConfig, provider: MarketDataProvider) -> None:
        self.config = config
        self.provider = provider

    def run(self) -> AgentRunResult:
        snapshot = self.provider.fetch_snapshot(self.config)
        stocks = score_stocks(snapshot, self.config.score_weights)
        themes = summarize_themes(self.config, stocks)
        markdown = generate_markdown_report(self.config, snapshot, stocks, themes)
        return AgentRunResult(
            snapshot=snapshot,
            stocks=stocks,
            themes=themes,
            markdown=markdown,
        )
