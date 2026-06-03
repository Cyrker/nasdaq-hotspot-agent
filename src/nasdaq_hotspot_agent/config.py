from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .models import EtfMember, UniverseMember


@dataclass(frozen=True)
class ThemeConfig:
    name: str
    description: str
    etfs: list[str]


@dataclass(frozen=True)
class AiConfig:
    enabled: bool = False
    provider: str = "openai_compatible"
    model: str = "gpt-4.1-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    api_key: str = ""
    temperature: float = 0.2
    max_tokens: int = 1200
    timeout_seconds: int = 60
    report_language: str = "zh-CN"


@dataclass(frozen=True)
class AgentConfig:
    title: str
    timezone: str
    max_themes: int
    max_stocks_per_theme: int
    score_weights: dict[str, float]
    universe: list[UniverseMember]
    etfs: list[EtfMember]
    themes: dict[str, ThemeConfig]
    ai: AiConfig


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _as_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def load_config(path: str | Path) -> AgentConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    report = data["report"]
    ai_data = data.get("ai", {})

    core = [
        UniverseMember(
            ticker=item["ticker"],
            company=item["company"],
            theme_tags=list(item["theme_tags"]),
            is_core=True,
        )
        for item in data["core_universe"]
    ]
    extended = [
        UniverseMember(
            ticker=item["ticker"],
            company=item["company"],
            theme_tags=list(item["theme_tags"]),
            is_core=False,
        )
        for item in data["extended_universe"]
    ]
    etfs = [
        EtfMember(
            ticker=item["ticker"],
            name=item["name"],
            theme_tags=list(item["theme_tags"]),
        )
        for item in data["etfs"]
    ]
    themes = {
        name: ThemeConfig(
            name=name,
            description=item["description"],
            etfs=list(item.get("etfs", [])),
        )
        for name, item in data["themes"].items()
    }

    return AgentConfig(
        title=report["title"],
        timezone=report["timezone"],
        max_themes=_as_int(report.get("max_themes"), 6),
        max_stocks_per_theme=_as_int(report.get("max_stocks_per_theme"), 8),
        score_weights=dict(data["score_weights"]),
        universe=core + extended,
        etfs=etfs,
        themes=themes,
        ai=AiConfig(
            enabled=_as_bool(ai_data.get("enabled"), False),
            provider=str(ai_data.get("provider", "openai_compatible")),
            model=str(ai_data.get("model", "gpt-4.1-mini")),
            base_url=str(ai_data.get("base_url", "https://api.openai.com/v1")),
            api_key_env=str(ai_data.get("api_key_env", "OPENAI_API_KEY")),
            api_key=str(ai_data.get("api_key", "")),
            temperature=_as_float(ai_data.get("temperature"), 0.2),
            max_tokens=_as_int(ai_data.get("max_tokens"), 1200),
            timeout_seconds=_as_int(ai_data.get("timeout_seconds"), 60),
            report_language=str(ai_data.get("report_language", "zh-CN")),
        ),
    )
