from __future__ import annotations

from .config import AgentConfig
from .models import MarketSnapshot, StockScore, ThemeSummary


def generate_markdown_report(
    config: AgentConfig,
    snapshot: MarketSnapshot,
    stocks: list[StockScore],
    themes: list[ThemeSummary],
) -> str:
    date_text = snapshot.as_of.strftime("%Y-%m-%d %H:%M %Z")
    lines: list[str] = [
        f"# {config.title}",
        "",
        f"- 数据截止：{date_text}",
        "- 数据状态：MVP 模拟数据，后续需接入真实行情和新闻源",
        "",
        "## 一句话总结",
        "",
        build_one_line_summary(snapshot, themes),
        "",
        "## 大盘背景",
        "",
    ]

    for name, change in snapshot.index_changes.items():
        lines.append(f"- {name}: {format_pct(change)}")

    if snapshot.macro_notes:
        lines.append("")
        lines.append("## 宏观和市场环境")
        lines.append("")
        for note in snapshot.macro_notes:
            lines.append(f"- {note}")

    lines.extend(["", "## 权重股贡献榜", ""])
    lines.append("| 股票 | 公司 | 权重 | 涨跌幅 | 成交量 | 新闻数 | 热点分 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for stock in stocks[:10]:
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{stock.ticker}`",
                    stock.company,
                    f"{stock.index_weight_pct:.2f}%",
                    format_pct(stock.price_change_pct),
                    f"{stock.volume_ratio:.1f}x",
                    str(stock.news_count),
                    f"{stock.score:.1f}",
                ]
            )
            + " |"
        )

    lines.extend(["", "## 今日热点主题", ""])
    for idx, theme in enumerate(themes, start=1):
        stock_text = ", ".join(f"`{stock.ticker}`" for stock in theme.related_stocks)
        etf_text = ", ".join(
            f"`{etf.ticker}` - {etf.name}" for etf in theme.related_etfs
        )
        lines.extend(
            [
                f"### {idx}. {theme.name}",
                "",
                f"- 热度：{theme.heat_level}，评分 {theme.score:.1f}",
                f"- 逻辑：{theme.description}",
                f"- 相关个股：{stock_text}",
                f"- 相关 ETF / 基金：{etf_text or '暂无配置'}",
                "- 触发因素：",
            ]
        )
        for catalyst in theme.catalysts:
            lines.append(f"  - {catalyst}")
        lines.append("")

    lines.extend(
        [
            "## 明日关注",
            "",
            "- 核心权重股是否继续跑赢 S&P 500。",
            "- 半导体 ETF 是否继续强于 QQQ。",
            "- AI 算力链的上涨是由单一龙头驱动，还是扩散到设备、存储、网络和软件。",
            "- 消费科技股如果继续分化，需要区分电商、零售和电动车的独立原因。",
            "",
            "## 风险提示",
            "",
            "- 本报告用于信息整理，不构成投资建议。",
            "- MVP 当前使用模拟数据，真实使用前必须接入可验证数据源。",
            "- 权重股估值和集中度较高，指数波动可能被少数股票放大。",
        ]
    )

    return "\n".join(lines) + "\n"


def build_one_line_summary(snapshot: MarketSnapshot, themes: list[ThemeSummary]) -> str:
    if not themes:
        return "今日暂无明确热点，建议等待真实行情和新闻源接入后重新评估。"

    ndx = snapshot.index_changes.get("Nasdaq-100", 0.0)
    spx = snapshot.index_changes.get("S&P 500", 0.0)
    top_names = "、".join(theme.name for theme in themes[:3])
    relative = "强于" if ndx > spx else "弱于"
    return (
        f"Nasdaq-100 今日{format_pct(ndx)}，{relative} S&P 500，"
        f"热点集中在{top_names}。"
    )


def format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"
