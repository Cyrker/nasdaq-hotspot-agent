from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..config import AiConfig
from ..models import MarketSnapshot, StockScore, ThemeSummary
from .base import AiProviderError, ReportRefiner


class OpenAICompatibleRefiner(ReportRefiner):
    """Chat Completions client for OpenAI and compatible providers."""

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    def refine(
        self,
        snapshot: MarketSnapshot,
        stocks: list[StockScore],
        themes: list[ThemeSummary],
    ) -> str:
        api_key = self._api_key()
        if not api_key:
            raise AiProviderError(
                f"AI 已启用，但未配置 API Key。请设置 {self.config.api_key_env} 或 ai_api_key。"
            )
        if not self.config.model:
            raise AiProviderError("AI 已启用，但未配置模型名称。")

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": self._user_payload(snapshot, stocks, themes)},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        response = self._post_json(self._chat_completions_url(), payload, api_key)
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AiProviderError(f"AI provider 返回格式不符合 Chat Completions: {exc}") from exc
        if not isinstance(content, str) or not content.strip():
            raise AiProviderError("AI provider 返回了空内容。")
        return content.strip()

    def _api_key(self) -> str:
        if self.config.api_key:
            return self.config.api_key.strip()
        if self.config.api_key_env:
            return os.getenv(self.config.api_key_env, "").strip()
        return ""

    def _chat_completions_url(self) -> str:
        base_url = self.config.base_url.rstrip("/")
        if base_url.endswith("/chat/completions"):
            return base_url
        return f"{base_url}/chat/completions"

    def _post_json(self, url: str, payload: dict[str, Any], api_key: str) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise AiProviderError(f"AI provider HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise AiProviderError(f"AI provider 连接失败: {exc.reason}") from exc
        except TimeoutError as exc:
            raise AiProviderError("AI provider 请求超时。") from exc

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AiProviderError(f"AI provider 返回非 JSON 内容: {text[:200]}") from exc
        if not isinstance(parsed, dict):
            raise AiProviderError("AI provider 返回内容不是 JSON object。")
        return parsed

    def _system_prompt(self) -> str:
        return (
            "你是一个美股市场信息整理助手。你的任务是把结构化行情和事件压缩成"
            "中文纳指权重股热点日报。不要给买入、卖出、目标价或仓位建议。"
            "必须区分事实、市场关注点和风险。输出要精炼，适合 QQ 群阅读。"
        )

    def _user_payload(
        self,
        snapshot: MarketSnapshot,
        stocks: list[StockScore],
        themes: list[ThemeSummary],
    ) -> str:
        data = {
            "language": self.config.report_language,
            "as_of": snapshot.as_of.isoformat(),
            "index_changes": snapshot.index_changes,
            "macro_notes": snapshot.macro_notes,
            "top_stocks": [
                {
                    "ticker": stock.ticker,
                    "company": stock.company,
                    "score": stock.score,
                    "index_weight_pct": stock.index_weight_pct,
                    "price_change_pct": stock.price_change_pct,
                    "volume_ratio": stock.volume_ratio,
                    "news_count": stock.news_count,
                    "themes": stock.theme_tags,
                    "catalysts": stock.catalysts,
                }
                for stock in stocks[:12]
            ],
            "themes": [
                {
                    "name": theme.name,
                    "heat_level": theme.heat_level,
                    "score": theme.score,
                    "description": theme.description,
                    "stocks": [stock.ticker for stock in theme.related_stocks],
                    "etfs": [etf.ticker for etf in theme.related_etfs],
                    "catalysts": theme.catalysts,
                }
                for theme in themes
            ],
        }
        return (
            "请基于以下 JSON 生成一个精炼版日报，格式固定为：\n"
            "1. 一句话总结\n"
            "2. 3-5 个热点主题，每个主题包含：核心逻辑、相关个股、相关 ETF、风险\n"
            "3. 明日关注\n\n"
            f"{json.dumps(data, ensure_ascii=False, indent=2)}"
        )
