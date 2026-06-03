from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import AgentConfig
from ..models import MarketSnapshot


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_snapshot(self, config: AgentConfig) -> MarketSnapshot:
        """Fetch a market snapshot for the configured universe."""
