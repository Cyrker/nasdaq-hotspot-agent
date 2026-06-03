from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import MarketSnapshot, StockScore, ThemeSummary


class AiProviderError(RuntimeError):
    """Raised when the configured AI provider cannot produce a response."""


class ReportRefiner(ABC):
    @abstractmethod
    def refine(
        self,
        snapshot: MarketSnapshot,
        stocks: list[StockScore],
        themes: list[ThemeSummary],
    ) -> str:
        """Return a concise natural-language report section."""
