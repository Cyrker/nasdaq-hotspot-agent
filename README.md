# Nasdaq Hotspot Agent

这是一个“纳指权重股热点日报”Agent 的最小可运行框架。

第一版目标不是预测涨跌，也不是自动荐股，而是每天自动整理：

- Nasdaq-100 / QQQ 权重股表现
- 重要个股异动
- 热点主题
- 对应股票和 ETF
- 新闻/财报/宏观催化
- 风险和次日关注点

当前版本使用模拟数据跑通流程，后续可以替换为真实行情、新闻、SEC、ETF 持仓等数据源。

## 快速运行

在本目录运行：

```powershell
$env:PYTHONPATH="src"
python -m nasdaq_hotspot_agent.cli --config config/watchlist.json --output reports/latest.md
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
/mh_now              立即生成日报并发回当前会话
/mh_push_now         立即生成日报并推送到已绑定 QQ 群
```

关键配置：

- `admin_qqs`：允许执行管理命令的 QQ 号。
- `target_umos`：目标 QQ 群会话，建议用 `/mh_bind_group` 自动写入。
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

AI 配置优先级：

```text
AstrBot WebUI 配置 > config/watchlist.json 默认配置
```

如果 `ai_enabled=true` 但 API Key 或服务不可用，插件会回退到模板摘要，并在日报顶部显示 AI 失败原因。

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
        mock.py             # 模拟数据源
```

## 后续接真实数据源

建议按这个顺序替换：

1. 行情数据源：指数、个股涨跌幅、成交量、ETF 表现。
2. 新闻数据源：公司新闻、宏观新闻、财报事件。
3. QQQ / Nasdaq-100 持仓权重：动态更新核心权重股。
4. SEC EDGAR：8-K、10-Q、10-K、S-1 等公告。
5. LLM 精炼层：把结构化事件压缩成中文日报。

## 推荐日报时间

- 北京时间 06:00：生成前一美股交易日盘后日报。
- 北京时间 20:00：可选生成盘前简报。

## 当前限制

- 数据是模拟的。
- 不包含投资建议。
- 不做自动交易。
- 权重和行情需要后续接 API 才能反映真实市场。
