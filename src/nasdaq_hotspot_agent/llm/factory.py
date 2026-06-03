from __future__ import annotations

from typing import TYPE_CHECKING

from .base import ReportRefiner
from .openai_compatible import OpenAICompatibleRefiner

if TYPE_CHECKING:
    from ..config import AiConfig


def create_refiner(config: "AiConfig") -> ReportRefiner | None:
    if not config.enabled:
        return None

    provider = config.provider.strip().lower()
    if provider in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleRefiner(config)
    raise ValueError(f"Unsupported AI provider: {config.provider}")
