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
class AgentConfig:
    title: str
    timezone: str
    max_themes: int
    max_stocks_per_theme: int
    score_weights: dict[str, float]
    universe: list[UniverseMember]
    etfs: list[EtfMember]
    themes: dict[str, ThemeConfig]


def load_config(path: str | Path) -> AgentConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    report = data["report"]

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
        max_themes=int(report["max_themes"]),
        max_stocks_per_theme=int(report["max_stocks_per_theme"]),
        score_weights=dict(data["score_weights"]),
        universe=core + extended,
        etfs=etfs,
        themes=themes,
    )
