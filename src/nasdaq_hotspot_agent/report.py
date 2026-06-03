from __future__ import annotations

from .config import AgentConfig
from .models import MarketSnapshot, StockScore, ThemeSummary


def generate_markdown_report(
    config: AgentConfig,
    snapshot: MarketSnapshot,
    stocks: list[StockScore],
    themes: list[ThemeSummary],
    ai_summary: str | None = None,
    ai_error: str | None = None,
) -> str:
    date_text = snapshot.as_of.strftime("%Y-%m-%d %H:%M %Z")
    lines: list[str] = [
        f"# {config.title}",
        "",
        f"- 数据截止：{date_text}",
        f"- 数据状态：{build_data_status(snapshot)}",
        f"- AI 精炼：{build_ai_status(config, ai_summary, ai_error)}",
        "",
        "## 精炼摘要",
        "",
        ai_summary or build_one_line_summary(snapshot, themes),
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

    if snapshot.provider_notes:
        lines.append("")
        lines.append("## 数据源状态")
        lines.append("")
        for note in snapshot.provider_notes:
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

    if snapshot.news_items:
        lines.extend(["", "## 重要来源证据", ""])
        for idx, item in enumerate(snapshot.news_items[:10], start=1):
            symbols = ", ".join(item.symbols) or "未匹配"
            url_text = f" - {item.url}" if should_include_urls(config) and item.url else ""
            lines.append(
                f"{idx}. [{item.confidence}] {item.title} "
                f"({item.provider}, {item.source}, symbols: {symbols}){url_text}"
            )
        lines.append("")

    lines.extend(["## 明日关注", ""])
    for item in build_tomorrow_watch(snapshot, stocks, themes):
        lines.append(f"- {item}")

    lines.extend(
        [
            "",
            "## 风险提示",
            "",
            "- 本报告用于信息整理，不构成投资建议。",
            "- 行情和新闻源可能存在延迟、摘要截断或 provider 回退，关键判断需要核对原始来源。",
            "- 权重股估值和集中度较高，指数波动可能被少数股票放大。",
        ]
    )

    return "\n".join(lines) + "\n"


def generate_plain_text_report(
    config: AgentConfig,
    snapshot: MarketSnapshot,
    stocks: list[StockScore],
    themes: list[ThemeSummary],
    ai_summary: str | None = None,
    ai_error: str | None = None,
) -> str:
    date_text = snapshot.as_of.strftime("%Y-%m-%d %H:%M %Z")
    lines: list[str] = [
        config.title,
        "",
        f"数据截止：{date_text}",
        f"数据状态：{build_data_status(snapshot)}",
        f"AI 精炼：{build_ai_status(config, ai_summary, ai_error)}",
        "",
        "精炼摘要",
        sanitize_plain_text(ai_summary or build_one_line_summary(snapshot, themes)),
        "",
        "大盘背景",
    ]

    for name, change in snapshot.index_changes.items():
        lines.append(f"{name}：{format_pct(change)}")

    if snapshot.macro_notes:
        lines.extend(["", "宏观和市场环境"])
        for idx, note in enumerate(snapshot.macro_notes, start=1):
            lines.append(f"{idx}. {note}")

    if snapshot.provider_notes:
        lines.extend(["", "数据源状态"])
        for idx, note in enumerate(snapshot.provider_notes, start=1):
            lines.append(f"{idx}. {note}")

    lines.extend(["", "权重股热点榜"])
    for idx, stock in enumerate(stocks[:8], start=1):
        lines.append(
            f"{idx}. {stock.ticker} {stock.company}："
            f"权重 {stock.index_weight_pct:.2f}%，"
            f"涨跌 {format_pct(stock.price_change_pct)}，"
            f"成交 {stock.volume_ratio:.1f}x，"
            f"热点分 {stock.score:.1f}"
        )

    lines.extend(["", "今日热点主题"])
    for idx, theme in enumerate(themes, start=1):
        stocks_text = "、".join(stock.ticker for stock in theme.related_stocks)
        etfs_text = "；".join(
            f"{etf.ticker} {etf.name}" for etf in theme.related_etfs
        )
        lines.extend(
            [
                f"{idx}. {theme.name}（{theme.heat_level}，{theme.score:.1f}）",
                f"逻辑：{theme.description}",
                f"相关个股：{stocks_text or '暂无'}",
                f"相关 ETF / 基金：{etfs_text or '暂无配置'}",
                "触发因素：",
            ]
        )
        for catalyst_idx, catalyst in enumerate(theme.catalysts, start=1):
            lines.append(f"{catalyst_idx}. {catalyst}")
        lines.append("")

    if snapshot.news_items:
        lines.extend(["重要来源证据"])
        for idx, item in enumerate(snapshot.news_items[:8], start=1):
            symbols = "、".join(item.symbols) or "未匹配"
            lines.append(
                f"{idx}. {item.title}（{item.provider}，{item.source}，依据：{item.confidence}，相关：{symbols}）"
            )
            if should_include_urls(config) and item.url:
                lines.append(item.url)
        lines.append("")

    lines.extend(["明日关注"])
    for idx, item in enumerate(build_tomorrow_watch(snapshot, stocks, themes), start=1):
        lines.append(f"{idx}. {item}")

    lines.extend(
        [
            "",
            "风险提示",
            "本报告用于信息整理，不构成投资建议。",
            "行情和新闻源可能存在延迟、摘要截断或 provider 回退，关键判断需要核对原始来源。",
        ]
    )

    return "\n".join(trim_trailing_blank_lines(lines)) + "\n"


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


def build_data_status(snapshot: MarketSnapshot) -> str:
    notes = list(snapshot.provider_notes)
    stooq_notes = [note for note in notes if note.startswith("Stooq market data:")]
    news_notes = [
        note
        for note in notes
        if note.startswith(("Marketaux:", "Alpha Vantage:", "Nasdaq RSS:", "SEC EDGAR:"))
    ]

    market_status = "行情：当前 provider 未返回外部行情状态"
    if stooq_notes:
        update_note = next(
            (note for note in stooq_notes if "updated" in note),
            "",
        )
        skipped_note = next(
            (note for note in stooq_notes if "skipped" in note),
            "",
        )
        fallback_note = next(
            (note for note in stooq_notes if "fell back" in note),
            "",
        )
        if skipped_note:
            market_status = "行情：Stooq 未配置 apikey，已回退样例行情"
        elif update_note:
            stock_count, etf_count = parse_stooq_update_counts(update_note)
            if stock_count == 0 and etf_count == 0:
                market_status = "行情：Stooq 未拉到有效日线，已回退样例行情"
            elif fallback_note:
                market_status = (
                    f"行情：Stooq 已更新 {stock_count} 只股票、{etf_count} 个 ETF，"
                    "未更新标的回退样例行情"
                )
            else:
                market_status = (
                    f"行情：Stooq 已更新 {stock_count} 只股票、{etf_count} 个 ETF"
                )

    if not news_notes:
        return f"{market_status}；新闻/公告：未返回外部源状态"

    active_news = [
        note
        for note in news_notes
        if "disabled" not in note
        and "skipped" not in note
        and "failed" not in note
    ]
    if active_news:
        return f"{market_status}；新闻/公告：已拉取外部源"
    return f"{market_status}；新闻/公告：外部源未启用或未配置"


def parse_stooq_update_counts(note: str) -> tuple[int, int]:
    parts = note.split(":", 1)[-1]
    numbers: list[int] = []
    for token in parts.replace(",", " ").split():
        try:
            numbers.append(int(token))
        except ValueError:
            continue
    stock_count = numbers[0] if len(numbers) >= 1 else 0
    etf_count = numbers[1] if len(numbers) >= 2 else 0
    return stock_count, etf_count


def build_tomorrow_watch(
    snapshot: MarketSnapshot,
    stocks: list[StockScore],
    themes: list[ThemeSummary],
) -> list[str]:
    items: list[str] = []
    core_stocks = [stock for stock in stocks if stock.is_core] or stocks
    core_text = format_stock_tickers(core_stocks, limit=4)
    ndx = snapshot.index_changes.get(
        "Nasdaq-100", snapshot.index_changes.get("QQQ", 0.0)
    )
    spx = snapshot.index_changes.get("S&P 500", 0.0)
    relative_gap = ndx - spx
    if core_text:
        if relative_gap >= 0.2:
            items.append(
                f"Nasdaq-100 今日较 S&P 500 强 {relative_gap:.2f} 个百分点，跟踪 {core_text} 是否继续贡献指数相对收益。"
            )
        elif relative_gap <= -0.2:
            items.append(
                f"Nasdaq-100 今日较 S&P 500 弱 {abs(relative_gap):.2f} 个百分点，优先看 {core_text} 是否止跌或继续拖累指数。"
            )
        else:
            items.append(
                f"Nasdaq-100 与 S&P 500 强弱接近，观察 {core_text} 能否重新拉开权重科技股溢价。"
            )

    if themes:
        top_theme = themes[0]
        theme_stocks = format_stock_tickers(top_theme.related_stocks, limit=4)
        catalyst = short_text(top_theme.catalysts[0], limit=64) if top_theme.catalysts else ""
        if catalyst:
            items.append(
                f"「{top_theme.name}」是最高热度主题，关注 {theme_stocks or '相关成分股'} 的新闻/公告是否继续验证：{catalyst}。"
            )
        else:
            items.append(
                f"「{top_theme.name}」是最高热度主题，关注 {theme_stocks or '相关成分股'} 是否继续放量。"
            )

    etf_by_ticker = {etf.ticker: etf for etf in snapshot.etfs}
    qqq_change = etf_by_ticker.get("QQQ").price_change_pct if "QQQ" in etf_by_ticker else ndx
    semi_etfs = [
        etf
        for ticker in ("SMH", "SOXX")
        for etf in [etf_by_ticker.get(ticker)]
        if etf is not None
    ]
    if semi_etfs:
        semi_avg = sum(etf.price_change_pct for etf in semi_etfs) / len(semi_etfs)
        semi_gap = semi_avg - qqq_change
        semi_text = "、".join(
            f"{etf.ticker} {format_pct(etf.price_change_pct)}" for etf in semi_etfs
        )
        semi_stocks = [
            stock
            for stock in stocks
            if "半导体" in stock.theme_tags or "AI 算力" in stock.theme_tags
        ]
        semi_stock_text = format_stock_tickers(semi_stocks, limit=4)
        if semi_gap >= 0.5:
            items.append(
                f"半导体 ETF（{semi_text}）明显强于 QQQ {format_pct(qqq_change)}，观察 {semi_stock_text or '芯片链'} 是否继续扩散。"
            )
        elif semi_gap <= -0.5:
            items.append(
                f"半导体 ETF（{semi_text}）弱于 QQQ {format_pct(qqq_change)}，观察 {semi_stock_text or '芯片链'} 是否从热点降温。"
            )
        else:
            items.append(
                f"半导体 ETF（{semi_text}）与 QQQ {format_pct(qqq_change)} 差距不大，观察芯片链能否走出独立强弱。"
            )

    movers = sorted(
        [
            stock
            for stock in stocks
            if abs(stock.price_change_pct) >= 3.0 or stock.volume_ratio >= 1.3
        ],
        key=lambda stock: (
            abs(stock.price_change_pct),
            stock.volume_ratio,
            stock.score,
        ),
        reverse=True,
    )
    gainers = [stock for stock in movers if stock.price_change_pct > 0]
    decliners = [stock for stock in movers if stock.price_change_pct < 0]
    if gainers and decliners:
        items.append(
            f"高波动个股出现分化：上涨端 {format_stock_tickers(gainers, limit=3)}，下跌端 {format_stock_tickers(decliners, limit=3)}，明日看资金是轮动还是回到单一主线。"
        )
    elif gainers:
        items.append(
            f"强势个股 {format_stock_tickers(gainers, limit=4)} 是否继续放量，需要区分真实催化和单日价格跳动。"
        )
    elif decliners:
        items.append(
            f"弱势个股 {format_stock_tickers(decliners, limit=4)} 是否继续拖累主题热度，需要核对是否有基本面事件。"
        )

    sec_symbols = sorted(
        {
            symbol
            for item in snapshot.news_items
            if item.source_type == "sec_filing" or item.provider == "sec_edgar"
            for symbol in item.symbols
        }
    )
    if sec_symbols:
        items.append(
            f"SEC 官方文件出现 {format_symbols(sec_symbols, limit=4)}，优先核对 filing 原文对业绩、指引或风险披露的影响。"
        )
    else:
        symbol_counts: dict[str, int] = {}
        for item in snapshot.news_items:
            for symbol in item.symbols:
                symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        news_text = format_symbol_counts(symbol_counts, limit=4)
        if news_text:
            items.append(
                f"新闻线索最密集的是 {news_text}，优先核对原文是否有实质催化，避免只按标题判断。"
            )

    if not items:
        items.append("新闻和行情线索不足，优先等待官方公告、财报日程或主流媒体原文确认。")

    return unique_items(items)[:4]


def format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.2f}%"


def format_stock_tickers(stocks: list[StockScore], limit: int = 4) -> str:
    return "、".join(stock.ticker for stock in stocks[:limit])


def format_symbols(symbols: list[str], limit: int = 4) -> str:
    return "、".join(symbols[:limit])


def format_symbol_counts(symbol_counts: dict[str, int], limit: int = 4) -> str:
    sorted_items = sorted(
        symbol_counts.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )[:limit]
    return "、".join(f"{symbol}({count})" for symbol, count in sorted_items)


def short_text(value: str, limit: int = 64) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def unique_items(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def build_ai_status(
    config: AgentConfig,
    ai_summary: str | None,
    ai_error: str | None,
) -> str:
    ai_config = getattr(config, "ai", None)
    if not ai_config or not ai_config.enabled:
        return "未启用，使用模板摘要"
    if ai_summary:
        return f"已启用，provider={ai_config.provider}, model={ai_config.model}"
    return f"失败，已回退模板摘要：{ai_error or '未知错误'}"


def should_include_urls(config: AgentConfig) -> bool:
    news_config = getattr(config, "news", None)
    return bool(getattr(news_config, "include_urls", True))


def sanitize_plain_text(text: str) -> str:
    cleaned_lines: list[str] = []
    for raw_line in text.replace("\r\n", "\n").replace("\r", "\n").splitlines():
        line = raw_line.strip()
        while line.startswith("#"):
            line = line[1:].strip()
        if set(line) <= {"-", "|", ":", " "}:
            continue
        line = (
            line.replace("```", "")
            .replace("`", "")
            .replace("**", "")
            .replace("__", "")
            .replace("|", " / ")
        )
        if line.startswith(("- ", "* ")):
            line = line[2:].strip()
        cleaned_lines.append(line)
    return "\n".join(trim_trailing_blank_lines(cleaned_lines)).strip()


def trim_trailing_blank_lines(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines.pop()
    return lines
