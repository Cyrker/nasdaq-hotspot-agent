from __future__ import annotations

from datetime import datetime

from ..config import AgentConfig
from ..models import EtfSnapshot, MarketSnapshot, StockSnapshot
from ..timezones import load_timezone
from .base import MarketDataProvider


class MockMarketDataProvider(MarketDataProvider):
    """Deterministic sample data for framework validation."""

    SAMPLE = {
        "NVDA": (8.7, 3.4, 1.9, 8, ["AI 芯片订单预期升温", "数据中心资本开支继续被上修"]),
        "AAPL": (7.5, -0.6, 0.9, 3, ["市场等待新品和服务收入指引"]),
        "MSFT": (5.7, 1.2, 1.2, 5, ["云业务和 AI Copilot 关注度提升"]),
        "AMZN": (4.6, 2.0, 1.4, 5, ["AWS 增长预期改善", "电商消费数据强于预期"]),
        "TSLA": (3.8, -2.8, 1.8, 6, ["交付数据和价格策略引发分歧"]),
        "META": (3.5, 1.6, 1.1, 4, ["广告需求和 AI 推荐系统改善"]),
        "WMT": (3.4, 0.5, 0.8, 2, ["防御消费和会员业务保持稳定"]),
        "GOOGL": (3.4, 1.1, 1.0, 4, ["搜索广告和 AI 产品更新受关注"]),
        "GOOG": (3.2, 1.0, 1.0, 4, ["搜索广告和 AI 产品更新受关注"]),
        "AVGO": (3.0, 2.8, 1.7, 7, ["AI 网络芯片需求继续走强"]),
        "AMD": (1.7, 2.5, 1.6, 6, ["AI 加速器出货预期改善"]),
        "COST": (2.4, 0.8, 0.9, 2, ["会员零售韧性仍强"]),
        "NFLX": (1.9, -1.1, 1.1, 3, ["内容投入和订阅增长预期分化"]),
        "ADBE": (1.5, 1.9, 1.3, 5, ["生成式 AI 功能商业化进展"]),
        "CSCO": (1.2, 0.4, 0.8, 1, ["网络设备需求温和恢复"]),
        "TMUS": (1.8, 0.3, 0.7, 1, ["通信服务板块波动较低"]),
        "INTU": (1.4, 1.5, 1.2, 3, ["软件订阅和 AI 助手关注"]),
        "AMAT": (1.3, 2.2, 1.5, 4, ["半导体设备链条跟随芯片股走强"]),
        "ISRG": (1.2, -0.2, 0.8, 1, ["医疗科技板块表现平稳"]),
        "TXN": (1.1, 0.9, 1.0, 2, ["Analog 芯片周期修复预期"]),
        "PDD": (0.9, -1.8, 1.4, 4, ["中概消费平台波动加大"]),
        "ARM": (0.8, 3.1, 1.8, 5, ["AI 终端和服务器架构关注度提升"]),
        "MU": (0.9, 2.6, 1.7, 5, ["HBM 和存储周期改善预期"]),
        "PANW": (0.8, 1.7, 1.3, 3, ["企业安全预算保持韧性"]),
    }

    ETF_SAMPLE = {
        "QQQ": (1.3, 1.1),
        "QQQM": (1.3, 1.0),
        "SMH": (2.4, 1.5),
        "SOXX": (2.2, 1.4),
        "XLK": (1.1, 1.0),
        "IYW": (1.2, 1.0),
        "XLY": (-0.2, 0.9),
    }

    def fetch_snapshot(self, config: AgentConfig) -> MarketSnapshot:
        tz = load_timezone(config.timezone)
        stocks = []
        for member in config.universe:
            weight, move, volume, news_count, catalysts = self.SAMPLE.get(
                member.ticker,
                (0.2, 0.0, 1.0, 0, ["暂无明显催化"]),
            )
            stocks.append(
                StockSnapshot(
                    ticker=member.ticker,
                    company=member.company,
                    index_weight_pct=weight,
                    price_change_pct=move,
                    volume_ratio=volume,
                    news_count=news_count,
                    catalysts=list(catalysts),
                    theme_tags=member.theme_tags,
                    is_core=member.is_core,
                )
            )

        etfs = []
        for item in config.etfs:
            move, volume = self.ETF_SAMPLE.get(item.ticker, (0.0, 1.0))
            etfs.append(
                EtfSnapshot(
                    ticker=item.ticker,
                    name=item.name,
                    price_change_pct=move,
                    volume_ratio=volume,
                    theme_tags=item.theme_tags,
                )
            )

        return MarketSnapshot(
            as_of=datetime.now(tz),
            index_changes={
                "Nasdaq-100": 1.3,
                "QQQ": 1.3,
                "S&P 500": 0.5,
                "Dow Jones": -0.1,
            },
            stocks=stocks,
            etfs=etfs,
            macro_notes=[
                "市场继续交易 AI 资本开支和大型科技盈利韧性。",
                "S&P 500 表现弱于 Nasdaq-100，说明权重科技股是主要驱动。",
            ],
        )
