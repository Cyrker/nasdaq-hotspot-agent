from __future__ import annotations

from dataclasses import dataclass

from .config import AgentConfig
from .llm.base import AiProviderError
from .llm.factory import create_refiner
from .models import MarketSnapshot, StockScore, ThemeSummary
from .providers.base import MarketDataProvider
from .report import generate_markdown_report, generate_plain_text_report
from .scoring import score_stocks
from .themes import summarize_themes


@dataclass(frozen=True)
class AgentRunResult:
    snapshot: MarketSnapshot
    stocks: list[StockScore]
    themes: list[ThemeSummary]
    markdown: str
    plain_text: str
    ai_summary: str | None = None
    ai_error: str | None = None


class NasdaqHotspotAgent:
    def __init__(self, config: AgentConfig, provider: MarketDataProvider) -> None:
        self.config = config
        self.provider = provider

    def run(self) -> AgentRunResult:
        snapshot = self.provider.fetch_snapshot(self.config)
        stocks = score_stocks(snapshot, self.config.score_weights)
        themes = summarize_themes(self.config, stocks)
        ai_summary: str | None = None
        ai_error: str | None = None

        try:
            refiner = create_refiner(self.config.ai)
            if refiner:
                ai_summary = refiner.refine(snapshot, stocks, themes)
        except (AiProviderError, ValueError) as exc:
            ai_error = str(exc)

        markdown = generate_markdown_report(
            self.config,
            snapshot,
            stocks,
            themes,
            ai_summary=ai_summary,
            ai_error=ai_error,
        )
        plain_text = generate_plain_text_report(
            self.config,
            snapshot,
            stocks,
            themes,
            ai_summary=ai_summary,
            ai_error=ai_error,
        )
        return AgentRunResult(
            snapshot=snapshot,
            stocks=stocks,
            themes=themes,
            markdown=markdown,
            plain_text=plain_text,
            ai_summary=ai_summary,
            ai_error=ai_error,
        )
