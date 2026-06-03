# Nasdaq Hotspot Agent

这是一个“纳指权重股热点日报”Agent。

第一版目标不是预测涨跌，也不是自动荐股，而是每天自动整理：

- Nasdaq-100 / QQQ 权重股表现
- 重要个股异动
- 热点主题
- 对应股票和 ETF
- 新闻/财报/宏观催化
- 风险和次日关注点

当前版本已经接入免费优先的新闻/公告源聚合，并用 Stooq 免费日线 CSV 更新个股/ETF 涨跌和成交量。拉取失败的行情会回退到 mock 值。

## 快速运行

在本目录运行：

```powershell
$env:PYTHONPATH="src"
python -m nasdaq_hotspot_agent.cli --provider news --config config/watchlist.json --output reports/latest.md
```

生成结果：

```text
reports/latest.md
```

## AstrBot QQ 接入

推荐用 AstrBot 插件接入 QQ。插件只负责定时触发、命令管理和发送 QQ 消息；行情采集、热点评分、主题聚合和报告生成仍由 `src/nasdaq_hotspot_agent` 负责。

本仓库根目录已经包含 AstrBot 插件需要的文件：

```text
main.py              # AstrBot 插件入口
metadata.yaml        # 插件元信息
_conf_schema.json    # AstrBot WebUI 配置项
```

安装方式：

1. 在 AstrBot 插件安装地址中填写 GitHub 仓库地址。
2. 如果 AstrBot 所在环境无法访问 GitHub，把本目录放到 AstrBot 的插件目录后作为本地插件加载。

常用命令：

```text
/mh_bind_group       绑定当前 QQ 群为日报接收群
/mh_unbind_group     移除当前 QQ 群
/mh_status           查看插件状态
/mh_version          查看插件运行时版本和路径
/mh_now              立即生成日报并发回当前会话
/mh_push_now         立即生成日报并推送到已绑定 QQ 群
```

QQ 消息会使用纯文本模板：不发送 Markdown 表格、标题符号、反引号或富文本标记。长消息默认会在支持 OneBot v11 的 QQ 适配器上尝试用“合并转发”发送；不支持时自动回退普通文本分段。插件仍会把完整 Markdown 版本保存到 `latest_report_path`，方便归档或后续发布到其它支持 Markdown 的渠道。

判断本次是否使用真实行情，看日报顶部的“数据状态”和“数据源状态”。如果显示 `Stooq 已更新 ...`，说明涨跌幅和成交量已经来自 Stooq；如果显示 `Stooq 未配置 apikey` 或 `0 stocks updated`，则行情已回退样例数据，需要检查 `market_data_provider`、`market_data_stooq_api_key` 和 AstrBot 插件是否已重载。

关键配置：

- `admin_qqs`：允许执行管理命令的 QQ 号，多个 QQ 用英文逗号分隔。
- `target_umos`：目标 QQ 群会话，多个会话用英文逗号分隔；建议用 `/mh_bind_group` 自动写入。
- `market_data_provider`：`news` 为 Stooq 行情 + 真实新闻/公告；`mock_with_news` 为 mock 行情 + 真实新闻/公告；`mock` 为纯模拟数据。
- `market_data_stooq_api_key`：Stooq CSV 下载 apikey；留空时行情回退 mock。
- `news_enabled`：是否启用新闻/公告源聚合。
- `news_marketaux_enabled` / `news_marketaux_api_key`：Marketaux 新闻 API。
- `news_alpha_vantage_enabled` / `news_alpha_vantage_api_key`：Alpha Vantage NEWS_SENTIMENT。
- `news_alpha_vantage_topics`：Alpha Vantage topics，多个 topic 用英文逗号分隔。
- `news_nasdaq_rss_enabled`：Nasdaq RSS，默认开启，不需要 API Key。
- `sec_edgar_enabled` / `sec_edgar_user_agent`：SEC EDGAR 官方公告；建议把 `contact@example.com` 改成你的真实邮箱。
- `sec_edgar_forms`：关注的 SEC 表单，多个表单用英文逗号分隔。
- `auto_push_enabled`：是否每天自动推送。
- `daily_report_time`：每日推送时间，默认 `06:00`。
- `timezone`：默认 `Asia/Shanghai`。
- `agent_config_path`：热点 Agent 配置文件，默认 `config/watchlist.json`。
- `ai_enabled`：是否启用 AI 精炼摘要。
- `ai_provider`：AI 提供商类型，当前支持 `openai_compatible` 和 `openai`。
- `ai_model`：模型名称，例如 `gpt-4.1-mini` 或兼容服务提供的模型名。
- `ai_base_url`：API Base URL，OpenAI 默认 `https://api.openai.com/v1`。
- `ai_api_key`：API Key，可直接在 AstrBot 配置界面填写。
- `ai_api_key_env`：`ai_api_key` 留空时读取的环境变量名，默认 `OPENAI_API_KEY`。
- `message_delivery_mode`：QQ 发送模式，`auto` 为长消息自动合并转发，`plain` 为普通文本分段，`forward` 为强制合并转发。
- `forward_message_threshold_chars`：`auto` 模式下触发合并转发的字符数，默认 `1800`。
- `forward_node_chars`：合并转发中每个节点的最大字符数，默认 `1200`。
- `forward_sender_name` / `forward_sender_uin`：合并转发节点显示的昵称和 QQ 号。

AI 配置优先级：

```text
AstrBot WebUI 配置 > config/watchlist.json 默认配置
```

如果 `ai_enabled=true` 但 API Key 或服务不可用，插件会回退到模板摘要，并在日报顶部显示 AI 失败原因。

## 需要注册的网站

必需注册：

```text
AI 模型提供商
```

你已经选择 `mimo-v2.5-pro`，需要在对应模型服务商后台拿到：

```text
ai_base_url
ai_api_key
ai_model = mimo-v2.5-pro
```

建议注册：

```text
Stooq CSV apikey
Marketaux
Alpha Vantage
```

- Stooq：用于免费日线行情。打开 `https://stooq.com/q/d/?s=nvda.us&get_apikey`，按页面提示输入验证码，复制带 apikey 的 CSV 链接，把 apikey 填到 `market_data_stooq_api_key`。这不是常规账号注册，但需要手动拿 key。
- Marketaux：用于股票相关新闻线索。注册后把 key 填到 `news_marketaux_api_key`，再打开 `news_marketaux_enabled`。
- Alpha Vantage：用于 `NEWS_SENTIMENT` 新闻情绪和主题辅助。注册后把 key 填到 `news_alpha_vantage_api_key`，再打开 `news_alpha_vantage_enabled`。

不需要注册：

```text
Nasdaq RSS
SEC EDGAR
```

- Nasdaq RSS：默认开启，免费 RSS 源。
- SEC EDGAR：免费官方源，不需要 API Key，但请求时应配置真实 `sec_edgar_user_agent`，建议包含应用名和联系邮箱。

当前推荐最小配置：

```text
market_data_provider = news
market_data_stooq_api_key = 你的 Stooq apikey
news_enabled = true
news_nasdaq_rss_enabled = true
sec_edgar_enabled = true
sec_edgar_user_agent = nasdaq-hotspot-agent/0.1 your-email@example.com
news_marketaux_enabled = true
news_marketaux_api_key = 你的 Marketaux key
news_alpha_vantage_enabled = true
news_alpha_vantage_api_key = 你的 Alpha Vantage key
ai_enabled = true
ai_provider = openai_compatible
ai_model = mimo-v2.5-pro
ai_max_tokens = 1800
```

加载故障处理：

如果 AstrBot 报 `cannot import name 'AiConfig' from 'nasdaq_hotspot_agent.config'`，通常是插件更新不完整或旧文件缓存。请先在 AstrBot 插件页重载；如果仍失败，删除 `/AstrBot/data/plugins/nasdaq_hotspot_agent` 后用公开仓库地址重新安装。

如果 AstrBot 报 `'AgentRunResult' object has no attribute 'plain_text'`，也是插件目录半更新导致入口文件和 `src/` 版本不一致。`v0.1.2` 起入口会自动回退，把旧版 Markdown 报告清洗成 QQ 纯文本发送；仍建议删除插件目录后重新安装，保证所有文件版本一致。

## AI 提供商配置

默认配置位于 `config/watchlist.json`：

```json
{
  "ai": {
    "enabled": false,
    "provider": "openai_compatible",
    "model": "gpt-4.1-mini",
    "base_url": "https://api.openai.com/v1",
    "api_key_env": "OPENAI_API_KEY",
    "api_key": "",
    "temperature": 0.2,
    "max_tokens": 1200,
    "timeout_seconds": 60,
    "report_language": "zh-CN"
  }
}
```

本项目使用 Chat Completions 兼容接口：

```text
POST {ai_base_url}/chat/completions
```

因此也可以接入其它 OpenAI-compatible 服务，只要它支持相同接口。

## 目录结构

```text
nasdaq_hotspot_agent/
  main.py                    # AstrBot 插件入口
  metadata.yaml              # AstrBot 插件元信息
  _conf_schema.json          # AstrBot 配置项
  config/
    watchlist.json          # 关注股票、ETF、主题映射、评分参数
  reports/
    latest.md               # 运行后生成的日报
  src/
    nasdaq_hotspot_agent/
      cli.py                # 命令行入口
      pipeline.py           # Agent 主流程
      models.py             # 数据模型
      config.py             # 配置读取
      scoring.py            # 热点评分
      themes.py             # 主题聚合
      report.py             # Markdown 报告生成
      providers/
        base.py             # 数据源接口
        enriched.py         # 行情 + 新闻/公告增强 provider
        factory.py          # provider 工厂
        mock.py             # 模拟数据源
        news.py             # Marketaux / Alpha Vantage / Nasdaq RSS / SEC EDGAR 聚合
        stooq.py            # Stooq 免费日线行情 provider
```

## 数据源策略

本项目区分两种证据：

1. 行情背景：Stooq 免费日线 CSV，用于个股/ETF 涨跌幅和成交量相对 20 日均量。
2. 新闻线索：Marketaux、Alpha Vantage、Nasdaq RSS。它们主要提供标题、摘要、snippet、URL、发布时间、ticker/entity，不假设有完整正文。
3. 官方证据：SEC EDGAR。它提供 8-K、10-Q、10-K、S-1 等官方 filing，可信度最高。

AI 总结时会收到 evidence pack，并被提示区分新闻线索和官方证据。日报里会显示 provider 状态、重要来源证据、依据强度和 URL。

## 推荐日报时间

- 北京时间 06:00：生成前一美股交易日盘后日报。
- 北京时间 20:00：可选生成盘前简报。

## 当前限制

- 行情使用 Stooq 免费日线，失败时回退 mock；不是实时行情。
- 不包含投资建议。
- 不做自动交易。
- Nasdaq-100 / QQQ 权重仍是配置/样例权重，后续可接 QQQ/NDX 持仓源动态更新。
