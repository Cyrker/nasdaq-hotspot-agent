from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from ..config import AgentConfig
from ..models import NewsArticle, UniverseMember


@dataclass(frozen=True)
class NewsFetchResult:
    articles: list[NewsArticle]
    notes: list[str]


class NewsAggregator:
    def fetch(self, config: AgentConfig) -> NewsFetchResult:
        news_config = getattr(config, "news", None)
        if not news_config or not news_config.enabled:
            return NewsFetchResult([], ["新闻源未启用，使用行情和 mock 催化。"])

        cutoff = datetime.now(UTC) - timedelta(hours=news_config.lookback_hours)
        articles: list[NewsArticle] = []
        notes: list[str] = []

        provider_calls = [
            self._fetch_marketaux,
            self._fetch_alpha_vantage,
            self._fetch_nasdaq_rss,
            self._fetch_sec_edgar,
        ]
        for provider_call in provider_calls:
            try:
                provider_articles, provider_note = provider_call(config, cutoff)
                articles.extend(provider_articles)
                notes.append(provider_note)
            except Exception as exc:
                notes.append(f"{provider_call.__name__.replace('_fetch_', '')}: failed: {exc}")

        articles = self._dedupe_articles(articles)
        articles = self._attach_symbols_when_missing(articles, config.universe)
        articles = sorted(
            articles,
            key=lambda item: item.published_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )[: news_config.max_articles_per_run]
        return NewsFetchResult(articles, notes)

    def _fetch_marketaux(
        self,
        config: AgentConfig,
        cutoff: datetime,
    ) -> tuple[list[NewsArticle], str]:
        provider_config = config.news.marketaux
        if not provider_config.enabled:
            return [], "Marketaux: disabled"

        api_key = self._api_key(provider_config.api_key, provider_config.api_key_env)
        if not api_key:
            return [], f"Marketaux: skipped, missing {provider_config.api_key_env}"

        tickers = [item.ticker for item in config.universe]
        articles: list[NewsArticle] = []
        for batch in self._batches(tickers, max(1, provider_config.symbol_batch_size)):
            params = {
                "api_token": api_key,
                "symbols": ",".join(batch),
                "language": "en",
                "filter_entities": "true",
                "published_after": cutoff.strftime("%Y-%m-%dT%H:%M:%S"),
                "limit": max(1, provider_config.articles_per_request),
            }
            data = self._get_json(
                f"https://api.marketaux.com/v1/news/all?{urlencode(params)}",
                timeout=config.news.request_timeout_seconds,
            )
            for item in data.get("data", []) if isinstance(data, dict) else []:
                if not isinstance(item, dict):
                    continue
                symbols = []
                for entity in item.get("entities", []) or []:
                    symbol = str(entity.get("symbol") or "").upper().strip()
                    if symbol:
                        symbols.append(symbol)
                source = item.get("source") or ""
                source_name = source.get("domain") if isinstance(source, dict) else source
                articles.append(
                    NewsArticle(
                        provider="marketaux",
                        title=self._clean_text(item.get("title")),
                        summary=self._clean_text(
                            item.get("description") or item.get("snippet")
                        ),
                        url=str(item.get("url") or ""),
                        source=str(source_name or "Marketaux"),
                        published_at=self._parse_datetime(item.get("published_at")),
                        symbols=self._unique(symbols),
                        topics=[],
                        sentiment=self._as_float(item.get("sentiment_score")),
                        source_type="news_snippet",
                        confidence="medium",
                        full_text_available=False,
                    )
                )
        return articles, f"Marketaux: {len(articles)} articles"

    def _fetch_alpha_vantage(
        self,
        config: AgentConfig,
        cutoff: datetime,
    ) -> tuple[list[NewsArticle], str]:
        provider_config = config.news.alpha_vantage
        if not provider_config.enabled:
            return [], "Alpha Vantage: disabled"

        api_key = self._api_key(provider_config.api_key, provider_config.api_key_env)
        if not api_key:
            return [], f"Alpha Vantage: skipped, missing {provider_config.api_key_env}"

        tickers = [item.ticker for item in config.universe]
        articles: list[NewsArticle] = []
        for batch in self._batches(tickers, max(1, provider_config.ticker_batch_size)):
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ",".join(batch),
                "time_from": cutoff.strftime("%Y%m%dT%H%M"),
                "sort": "LATEST",
                "limit": max(1, provider_config.limit_per_request),
                "apikey": api_key,
            }
            if provider_config.topics:
                params["topics"] = ",".join(provider_config.topics)
            data = self._get_json(
                f"https://www.alphavantage.co/query?{urlencode(params)}",
                timeout=config.news.request_timeout_seconds,
            )
            for item in data.get("feed", []) if isinstance(data, dict) else []:
                if not isinstance(item, dict):
                    continue
                symbols = []
                for ticker_info in item.get("ticker_sentiment", []) or []:
                    symbol = str(ticker_info.get("ticker") or "").upper().strip()
                    if symbol:
                        symbols.append(symbol)
                topics = [
                    str(topic.get("topic") or "").strip()
                    for topic in item.get("topics", []) or []
                    if isinstance(topic, dict) and topic.get("topic")
                ]
                articles.append(
                    NewsArticle(
                        provider="alpha_vantage",
                        title=self._clean_text(item.get("title")),
                        summary=self._clean_text(item.get("summary")),
                        url=str(item.get("url") or ""),
                        source=str(item.get("source") or "Alpha Vantage"),
                        published_at=self._parse_alpha_time(item.get("time_published")),
                        symbols=self._unique(symbols),
                        topics=self._unique(topics),
                        sentiment=self._as_float(item.get("overall_sentiment_score")),
                        source_type="news_summary",
                        confidence="medium",
                        full_text_available=False,
                    )
                )
        return articles, f"Alpha Vantage: {len(articles)} articles"

    def _fetch_nasdaq_rss(
        self,
        config: AgentConfig,
        cutoff: datetime,
    ) -> tuple[list[NewsArticle], str]:
        provider_config = config.news.nasdaq_rss
        if not provider_config.enabled:
            return [], "Nasdaq RSS: disabled"

        feed_urls = list(provider_config.feed_urls or [])
        for member in config.universe[: max(0, provider_config.symbol_feed_limit)]:
            feed_urls.append(
                f"https://www.nasdaq.com/feed/rssoutbound?symbol={member.ticker}"
            )

        articles: list[NewsArticle] = []
        failures: list[str] = []
        for feed_url in self._unique(feed_urls):
            try:
                xml_text = self._get_text(
                    feed_url,
                    timeout=config.news.request_timeout_seconds,
                    headers={"User-Agent": "nasdaq-hotspot-agent/0.1"},
                )
                root = ET.fromstring(xml_text)
            except Exception as exc:
                failures.append(f"{feed_url}: {exc}")
                continue
            for item in root.findall(".//item"):
                published_at = self._parse_rss_time(self._node_text(item, "pubDate"))
                if published_at and published_at < cutoff:
                    continue
                title = self._clean_text(self._node_text(item, "title"))
                summary = self._clean_text(self._node_text(item, "description"))
                link = self._node_text(item, "link").strip()
                category = self._clean_text(self._node_text(item, "category"))
                articles.append(
                    NewsArticle(
                        provider="nasdaq_rss",
                        title=title,
                        summary=summary,
                        url=link,
                        source="Nasdaq",
                        published_at=published_at,
                        symbols=[],
                        topics=[category] if category else [],
                        source_type="rss_summary",
                        confidence="medium",
                        full_text_available=False,
                    )
                )
        note = f"Nasdaq RSS: {len(articles)} articles"
        if failures:
            note += f", {len(failures)} feed failures"
        return articles, note

    def _fetch_sec_edgar(
        self,
        config: AgentConfig,
        cutoff: datetime,
    ) -> tuple[list[NewsArticle], str]:
        provider_config = config.news.sec_edgar
        if not provider_config.enabled:
            return [], "SEC EDGAR: disabled"

        user_agent = provider_config.user_agent.strip()
        if not user_agent or "example.com" in user_agent:
            return [], "SEC EDGAR: skipped, configure a real sec_user_agent with email/contact"

        cik_by_ticker = self._sec_ticker_map(config.news.request_timeout_seconds, user_agent)
        articles: list[NewsArticle] = []
        forms = set(provider_config.forms or [])
        for member in config.universe[: max(1, provider_config.max_symbols)]:
            try:
                cik = cik_by_ticker.get(member.ticker.upper())
                if not cik:
                    continue
                data = self._get_json(
                    f"https://data.sec.gov/submissions/CIK{cik:010d}.json",
                    timeout=config.news.request_timeout_seconds,
                    headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
                )
            except Exception:
                continue
            recent = data.get("filings", {}).get("recent", {}) if isinstance(data, dict) else {}
            form_list = recent.get("form", []) or []
            accession_list = recent.get("accessionNumber", []) or []
            doc_list = recent.get("primaryDocument", []) or []
            filing_dates = recent.get("filingDate", []) or []
            accepted_times = recent.get("acceptanceDateTime", []) or []
            for idx, form in enumerate(form_list[:80]):
                if forms and form not in forms:
                    continue
                filed_at = self._parse_sec_time(
                    self._list_get(accepted_times, idx) or self._list_get(filing_dates, idx)
                )
                if filed_at and filed_at < cutoff:
                    continue
                accession = str(self._list_get(accession_list, idx) or "")
                primary_doc = str(self._list_get(doc_list, idx) or "")
                accession_path = accession.replace("-", "")
                url = (
                    f"https://www.sec.gov/Archives/edgar/data/{cik}/"
                    f"{accession_path}/{primary_doc}"
                    if accession and primary_doc
                    else ""
                )
                title = f"{member.ticker} filed {form}"
                summary = f"{member.company} submitted SEC form {form}."
                articles.append(
                    NewsArticle(
                        provider="sec_edgar",
                        title=title,
                        summary=summary,
                        url=url,
                        source="SEC EDGAR",
                        published_at=filed_at,
                        symbols=[member.ticker],
                        topics=[form],
                        source_type="sec_filing",
                        confidence="high",
                        full_text_available=True,
                    )
                )
                if len([a for a in articles if member.ticker in a.symbols]) >= 2:
                    break
        return articles, f"SEC EDGAR: {len(articles)} filings"

    def _sec_ticker_map(self, timeout: int, user_agent: str) -> dict[str, int]:
        data = self._get_json(
            "https://www.sec.gov/files/company_tickers.json",
            timeout=timeout,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )
        mapping: dict[str, int] = {}
        for item in data.values() if isinstance(data, dict) else []:
            if not isinstance(item, dict):
                continue
            ticker = str(item.get("ticker") or "").upper().strip()
            cik = item.get("cik_str")
            if ticker and cik is not None:
                mapping[ticker] = int(cik)
        return mapping

    def _attach_symbols_when_missing(
        self,
        articles: list[NewsArticle],
        universe: list[UniverseMember],
    ) -> list[NewsArticle]:
        next_articles: list[NewsArticle] = []
        known_tickers = {member.ticker.upper() for member in universe}
        for article in articles:
            symbols = [symbol for symbol in article.symbols if symbol in known_tickers]
            if not symbols:
                haystack = f"{article.title} {article.summary}".lower()
                for member in universe:
                    ticker = member.ticker.upper()
                    ticker_match = re.search(rf"\b{re.escape(ticker.lower())}\b", haystack)
                    company_match = member.company.lower() in haystack
                    if ticker_match or company_match:
                        symbols.append(ticker)
            next_articles.append(
                NewsArticle(
                    provider=article.provider,
                    title=article.title,
                    summary=article.summary,
                    url=article.url,
                    source=article.source,
                    published_at=article.published_at,
                    symbols=self._unique(symbols),
                    topics=article.topics,
                    sentiment=article.sentiment,
                    source_type=article.source_type,
                    confidence=article.confidence,
                    full_text_available=article.full_text_available,
                )
            )
        return next_articles

    def _dedupe_articles(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        deduped: list[NewsArticle] = []
        seen: set[str] = set()
        for article in articles:
            key = (article.url or article.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(article)
        return deduped

    def _get_json(
        self,
        url: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
    ) -> dict:
        text = self._get_text(url, timeout=timeout, headers=headers)
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}

    def _get_text(
        self,
        url: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
    ) -> str:
        request_headers = {
            "User-Agent": "nasdaq-hotspot-agent/0.1",
            "Accept": "application/json,text/xml,application/rss+xml,text/html;q=0.8,*/*;q=0.5",
        }
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers)
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:200]
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"connection failed: {exc.reason}") from exc

    def _api_key(self, explicit: str, env_name: str) -> str:
        return explicit.strip() or os.getenv(env_name, "").strip()

    def _batches(self, items: list[str], size: int) -> list[list[str]]:
        return [items[idx : idx + size] for idx in range(0, len(items), size)]

    def _clean_text(self, value: object) -> str:
        text = unescape(str(value or ""))
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _parse_datetime(self, value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except ValueError:
            return None

    def _parse_alpha_time(self, value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
        except ValueError:
            return None

    def _parse_rss_time(self, value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            parsed = parsedate_to_datetime(text)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            return None

    def _parse_sec_time(self, value: object) -> datetime | None:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    def _as_float(self, value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _node_text(self, item: ET.Element, tag: str) -> str:
        node = item.find(tag)
        return node.text if node is not None and node.text else ""

    def _list_get(self, values: list, idx: int) -> object:
        return values[idx] if idx < len(values) else None

    def _unique(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            value = str(item or "").strip()
            if value and value not in seen:
                result.append(value)
                seen.add(value)
        return result
