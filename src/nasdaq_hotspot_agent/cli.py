from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .pipeline import NasdaqHotspotAgent
from .providers.factory import create_market_data_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a Nasdaq-100 hotspot report."
    )
    parser.add_argument(
        "--config",
        default="config/watchlist.json",
        help="Path to the agent config JSON file.",
    )
    parser.add_argument(
        "--output",
        default="reports/latest.md",
        help="Path to write the generated Markdown report.",
    )
    parser.add_argument(
        "--provider",
        default="news",
        choices=["mock", "news", "mock_with_news", "enriched"],
        help="Market data provider to use.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    provider = create_market_data_provider(args.provider)
    agent = NasdaqHotspotAgent(config=config, provider=provider)
    result = agent.run()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result.markdown, encoding="utf-8")
    print(f"Wrote report: {output_path}")


if __name__ == "__main__":
    main()
