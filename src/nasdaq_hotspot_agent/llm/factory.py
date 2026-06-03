from __future__ import annotations

from ..config import AiConfig
from .base import ReportRefiner
from .openai_compatible import OpenAICompatibleRefiner


def create_refiner(config: AiConfig) -> ReportRefiner | None:
    if not config.enabled:
        return None

    provider = config.provider.strip().lower()
    if provider in {"openai", "openai_compatible", "openai-compatible"}:
        return OpenAICompatibleRefiner(config)
    raise ValueError(f"Unsupported AI provider: {config.provider}")
