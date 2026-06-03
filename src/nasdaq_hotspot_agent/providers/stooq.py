from __future__ import annotations

import csv
import os
from dataclasses import replace
from io import StringIO
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import AgentConfig
from ..models import EtfSnapshot, MarketSnapshot, StockSnapshot
from .base import MarketDataProvider


class StooqMarketDataProvider(MarketDataProvider):
    """Free delayed daily market data from Stooq CSV, with mock fallback."""

    def __init__(self, fallback_provider: MarketDataProvider) -> None:
        self.fallback_provider = fallback_provider

    def fetch_snapshot(self, config: AgentConfig) -> MarketSnapshot:
        snapshot = self.fallback_provider.fetch_snapshot(config)
        stooq_config = getattr(getattr(config, "market_data", None), "stooq", None)
        api_key = self._api_key(
            getattr(stooq_config, "api_key", ""),
            getattr(stooq_config, "api_key_env", "STOOQ_API_KEY"),
        )
        api_key_env = getattr(stooq_config, "api_key_env", "STOOQ_API_KEY")
        timeout = int(getattr(stooq_config, "timeout_seconds", 8) or 8)
        if not api_key:
            return replace(
                snapshot,
                provider_notes=[
                    *snapshot.provider_notes,
                    f"Stooq market data: skipped, missing {api_key_env}",
                ],
            )
        stock_notes: list[str] = []
        etf_notes: list[str] = []
        stocks = [
            self._replace_stock_snapshot(stock, stock_notes, api_key, timeout)
            for stock in snapshot.stocks
        ]
        etfs = [
            self._replace_etf_snapshot(etf, etf_notes, api_key, timeout)
            for etf in snapshot.etfs
        ]
        index_changes = dict(snapshot.index_changes)
        etf_change_by_ticker = {etf.ticker: etf.price_change_pct for etf in etfs}
        if "QQQ" in etf_change_by_ticker:
            index_changes["Nasdaq-100"] = etf_change_by_ticker["QQQ"]
            index_changes["QQQ"] = etf_change_by_ticker["QQQ"]
        if "SPY" in etf_change_by_ticker:
            index_changes["S&P 500"] = etf_change_by_ticker["SPY"]
        if "DIA" in etf_change_by_ticker:
            index_changes["Dow Jones"] = etf_change_by_ticker["DIA"]

        notes = [
            f"Stooq market data: {len(stock_notes)} stocks updated, {len(etf_notes)} ETFs updated"
        ]
        if not stock_notes and not etf_notes:
            notes.append(
                "Stooq market data: all symbols fell back to mock data; check apikey, network, or whether only the apikey value was configured"
            )
        elif len(stock_notes) < len(stocks) or len(etf_notes) < len(etfs):
            notes.append("Stooq market data: some symbols fell back to mock data")

        return replace(
            snapshot,
            index_changes=index_changes,
            stocks=stocks,
            etfs=etfs,
            provider_notes=[*snapshot.provider_notes, *notes],
        )

    def _replace_stock_snapshot(
        self,
        stock: StockSnapshot,
        notes: list[str],
        api_key: str,
        timeout: int,
    ) -> StockSnapshot:
        metrics = self._fetch_daily_metrics(stock.ticker, api_key, timeout)
        if not metrics:
            return stock
        notes.append(stock.ticker)
        return replace(
            stock,
            price_change_pct=metrics["price_change_pct"],
            volume_ratio=metrics["volume_ratio"],
        )

    def _replace_etf_snapshot(
        self,
        etf: EtfSnapshot,
        notes: list[str],
        api_key: str,
        timeout: int,
    ) -> EtfSnapshot:
        metrics = self._fetch_daily_metrics(etf.ticker, api_key, timeout)
        if not metrics:
            return etf
        notes.append(etf.ticker)
        return replace(
            etf,
            price_change_pct=metrics["price_change_pct"],
            volume_ratio=metrics["volume_ratio"],
        )

    def _fetch_daily_metrics(
        self,
        ticker: str,
        api_key: str,
        timeout: int,
    ) -> dict[str, float] | None:
        rows = self._fetch_daily_rows(ticker, api_key, timeout)
        if len(rows) < 2:
            return None
        last = rows[-1]
        previous = rows[-2]
        close = self._as_float(last.get("Close"))
        previous_close = self._as_float(previous.get("Close"))
        volume = self._as_float(last.get("Volume"))
        previous_volumes = [
            self._as_float(row.get("Volume"))
            for row in rows[-21:-1]
            if self._as_float(row.get("Volume")) > 0
        ]
        if close <= 0 or previous_close <= 0:
            return None
        avg_volume = (
            sum(previous_volumes) / len(previous_volumes)
            if previous_volumes
            else volume
        )
        return {
            "price_change_pct": round((close - previous_close) / previous_close * 100, 2),
            "volume_ratio": round(volume / avg_volume, 2) if avg_volume > 0 else 1.0,
        }

    def _fetch_daily_rows(
        self,
        ticker: str,
        api_key: str,
        timeout: int,
    ) -> list[dict[str, str]]:
        stooq_symbol = self._stooq_symbol(ticker)
        url = f"https://stooq.com/q/d/l/?{urlencode({'s': stooq_symbol, 'i': 'd', 'apikey': api_key})}"
        request = Request(url, headers={"User-Agent": "nasdaq-hotspot-agent/0.1"})
        try:
            with urlopen(request, timeout=timeout) as response:
                text = response.read().decode("utf-8", errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError):
            return []
        lowered = text.lower().strip()
        if (
            not lowered
            or lowered.startswith("no data")
            or "get your apikey" in lowered
        ):
            return []
        reader = csv.DictReader(StringIO(text))
        return [row for row in reader if row.get("Close") and row.get("Volume")]

    def _stooq_symbol(self, ticker: str) -> str:
        ticker = ticker.lower().replace(".", "-")
        if ticker.startswith("^"):
            return ticker
        return f"{ticker}.us"

    def _api_key(self, explicit: str, env_name: str) -> str:
        return str(explicit or "").strip() or os.getenv(env_name, "").strip()

    def _as_float(self, value: object) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0
