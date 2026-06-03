from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parent
SRC_DIR = PLUGIN_ROOT / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.star import Context, Star

from nasdaq_hotspot_agent.config import AgentConfig, AiConfig, load_config
from nasdaq_hotspot_agent.pipeline import NasdaqHotspotAgent
from nasdaq_hotspot_agent.providers.mock import MockMarketDataProvider
from nasdaq_hotspot_agent.timezones import load_timezone


class NasdaqHotspotReporter(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._daily_task: asyncio.Task[None] | None = asyncio.create_task(
            self._daily_loop()
        )

    def _get_bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _get_int(self, key: str, default: int) -> int:
        try:
            return max(1, int(self.config.get(key, default)))
        except (TypeError, ValueError):
            return default

    def _get_float(self, key: str, default: float) -> float:
        try:
            return float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default

    def _get_str(self, key: str, default: str = "") -> str:
        return str(self.config.get(key, default) or "").strip()

    def _normalize_list(self, value: Any) -> list[str]:
        if isinstance(value, str):
            raw_items = (
                value.replace("，", "\n")
                .replace(",", "\n")
                .replace(";", "\n")
                .replace("；", "\n")
                .splitlines()
            )
        elif isinstance(value, (list, tuple, set)):
            raw_items = value
        else:
            raw_items = []

        items: list[str] = []
        seen: set[str] = set()
        for raw_item in raw_items:
            item = str(raw_item or "").strip()
            if item and item not in seen:
                items.append(item)
                seen.add(item)
        return items

    def _admin_qqs(self) -> set[str]:
        return set(self._normalize_list(self.config.get("admin_qqs", "")))

    def _target_umos(self) -> list[str]:
        return self._normalize_list(self.config.get("target_umos", ""))

    def _save_target_umos(self, targets: list[str]) -> None:
        self.config["target_umos"] = "\n".join(self._normalize_list(targets))
        self.config.save_config()

    def _event_sender_id(self, event: AstrMessageEvent) -> str:
        with suppress(Exception):
            return str(event.get_sender_id() or "").strip()
        sender = getattr(getattr(event, "message_obj", None), "sender", None)
        for attr in ("user_id", "id", "qq"):
            value = getattr(sender, attr, None)
            if value:
                return str(value).strip()
        return ""

    def _is_admin_event(self, event: AstrMessageEvent) -> bool:
        with suppress(Exception):
            if event.is_admin():
                return True
        sender_id = self._event_sender_id(event)
        return bool(sender_id and sender_id in self._admin_qqs())

    def _permission_denied_message(self, event: AstrMessageEvent) -> str:
        sender_id = self._event_sender_id(event) or "未知"
        return f"没有权限执行热点日报命令。请在插件配置 admin_qqs 中添加你的 QQ：{sender_id}"

    def _config_path(self) -> Path:
        configured = self._get_str("agent_config_path", "config/watchlist.json")
        path = Path(configured)
        if not path.is_absolute():
            path = PLUGIN_ROOT / path
        return path

    def _output_path(self) -> Path:
        configured = self._get_str("latest_report_path", "reports/astrbot-latest.md")
        path = Path(configured)
        if not path.is_absolute():
            path = PLUGIN_ROOT / path
        return path

    def _load_agent_config(self) -> AgentConfig:
        base_config = load_config(self._config_path())
        base_ai = base_config.ai
        ai_config = AiConfig(
            enabled=self._get_bool("ai_enabled", base_ai.enabled),
            provider=self._get_str("ai_provider", base_ai.provider),
            model=self._get_str("ai_model", base_ai.model),
            base_url=self._get_str("ai_base_url", base_ai.base_url),
            api_key_env=self._get_str("ai_api_key_env", base_ai.api_key_env),
            api_key=self._get_str("ai_api_key", base_ai.api_key),
            temperature=self._get_float("ai_temperature", base_ai.temperature),
            max_tokens=self._get_int("ai_max_tokens", base_ai.max_tokens),
            timeout_seconds=self._get_int("ai_timeout_seconds", base_ai.timeout_seconds),
            report_language=self._get_str("ai_report_language", base_ai.report_language),
        )
        return replace(base_config, ai=ai_config)

    def _run_agent_sync(self) -> str:
        agent_config = self._load_agent_config()
        agent = NasdaqHotspotAgent(
            config=agent_config,
            provider=MockMarketDataProvider(),
        )
        result = agent.run()
        output_path = self._output_path()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result.markdown, encoding="utf-8")
        return result.markdown

    async def _generate_report(self) -> str:
        return await asyncio.to_thread(self._run_agent_sync)

    def _max_message_chars(self) -> int:
        return self._get_int("max_message_chars", 1800)

    def _chunk_text(self, text: str) -> list[str]:
        limit = self._max_message_chars()
        chunks: list[str] = []
        current = ""
        for line in text.splitlines():
            candidate = f"{current}\n{line}" if current else line
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = line
        if current:
            chunks.append(current)
        return chunks or [text[:limit]]

    async def _send_text_to_target(self, target: str, text: str) -> None:
        for chunk in self._chunk_text(text):
            sent = await self.context.send_message(target, MessageChain().message(chunk))
            if sent is False:
                raise RuntimeError("AstrBot 未找到目标会话")
            await asyncio.sleep(0.5)

    async def _broadcast_report(self, text: str) -> tuple[int, list[str]]:
        targets = self._target_umos()
        if not targets:
            raise RuntimeError("未绑定 QQ 群，无法推送热点日报")

        sent_count = 0
        failures: list[str] = []
        for target in targets:
            try:
                await self._send_text_to_target(target, text)
                sent_count += 1
            except Exception as exc:
                failures.append(f"{target}: {exc}")

        if failures:
            logger.warning(
                f"纳指热点日报部分推送失败: 成功 {sent_count} 个，失败 {len(failures)} 个；"
                f"{'; '.join(failures[:3])}"
            )
        return sent_count, failures

    def _today_key(self) -> str:
        tz = load_timezone(self._get_str("timezone", "Asia/Shanghai"))
        from datetime import datetime

        return datetime.now(tz).strftime("%Y-%m-%d")

    def _is_daily_due(self) -> bool:
        if not self._get_bool("enabled", True):
            return False
        if not self._get_bool("auto_push_enabled", False):
            return False

        tz = load_timezone(self._get_str("timezone", "Asia/Shanghai"))
        from datetime import datetime

        now = datetime.now(tz)
        today = now.strftime("%Y-%m-%d")
        if self._get_str("last_sent_date") == today:
            return False

        raw_time = self._get_str("daily_report_time", "06:00")
        try:
            hour_text, minute_text = raw_time.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
        except ValueError:
            hour, minute = 6, 0
        return (now.hour, now.minute) >= (hour, minute)

    def _mark_daily_sent(self) -> None:
        self.config["last_sent_date"] = self._today_key()
        self.config.save_config()

    async def _daily_loop(self) -> None:
        while True:
            try:
                if self._is_daily_due():
                    report = await self._generate_report()
                    sent_count, failures = await self._broadcast_report(report)
                    if sent_count > 0:
                        self._mark_daily_sent()
                    if failures:
                        logger.warning(f"纳指热点日报定时推送存在失败: {'; '.join(failures[:3])}")
                await asyncio.sleep(self._get_int("schedule_check_seconds", 60))
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(f"纳指热点日报定时任务失败: {exc}")
                await asyncio.sleep(self._get_int("failure_backoff_seconds", 300))

    @filter.command("mh_bind_group")
    async def bind_group(self, event: AstrMessageEvent):
        """把当前 QQ 群绑定为美股热点日报接收群。"""
        if not self._is_admin_event(event):
            yield event.plain_result(self._permission_denied_message(event))
            return

        group_id = str(getattr(event.message_obj, "group_id", "") or "").strip()
        if not group_id:
            yield event.plain_result("请在需要接收热点日报的 QQ 群里执行这个命令。")
            return

        current_target = str(event.unified_msg_origin or "").strip()
        targets = self._target_umos()
        if current_target in targets:
            yield event.plain_result(f"当前群已绑定，共 {len(targets)} 个群。")
            return

        targets.append(current_target)
        self._save_target_umos(targets)
        yield event.plain_result(f"已绑定当前群为热点日报接收群，共 {len(targets)} 个群。")

    @filter.command("mh_unbind_group")
    async def unbind_group(self, event: AstrMessageEvent):
        """从美股热点日报接收群移除当前 QQ 群。"""
        if not self._is_admin_event(event):
            yield event.plain_result(self._permission_denied_message(event))
            return

        current_target = str(event.unified_msg_origin or "").strip()
        targets = self._target_umos()
        next_targets = [target for target in targets if target != current_target]
        if len(next_targets) == len(targets):
            yield event.plain_result(f"当前群未绑定，共 {len(targets)} 个群。")
            return

        self._save_target_umos(next_targets)
        yield event.plain_result(f"已移除当前群，剩余 {len(next_targets)} 个群。")

    @filter.command("mh_status")
    async def status(self, event: AstrMessageEvent):
        """查看美股热点日报插件状态。"""
        if not self._is_admin_event(event):
            yield event.plain_result(self._permission_denied_message(event))
            return

        lines = [
            f"enabled: {self._get_bool('enabled', True)}",
            f"auto_push_enabled: {self._get_bool('auto_push_enabled', False)}",
            f"daily_report_time: {self._get_str('daily_report_time', '06:00')}",
            f"timezone: {self._get_str('timezone', 'Asia/Shanghai')}",
            f"ai_enabled: {self._get_bool('ai_enabled', False)}",
            f"ai_provider: {self._get_str('ai_provider', 'openai_compatible')}",
            f"ai_model: {self._get_str('ai_model', 'gpt-4.1-mini')}",
            f"ai_base_url: {self._get_str('ai_base_url', 'https://api.openai.com/v1')}",
            f"ai_api_key: {'已配置' if self._get_str('ai_api_key') else '未配置'}",
            f"ai_api_key_env: {self._get_str('ai_api_key_env', 'OPENAI_API_KEY')}",
            f"target_groups: {len(self._target_umos())}",
            f"admin_qqs: {len(self._admin_qqs())}",
            f"agent_config_path: {self._config_path()}",
            f"latest_report_path: {self._output_path()}",
            f"last_sent_date: {self._get_str('last_sent_date', '无')}",
        ]
        yield event.plain_result("\n".join(lines))

    @filter.command("mh_now")
    async def report_now(self, event: AstrMessageEvent):
        """立即生成一份热点日报并发回当前会话。"""
        if not self._is_admin_event(event):
            yield event.plain_result(self._permission_denied_message(event))
            return

        try:
            report = await self._generate_report()
        except Exception as exc:
            logger.warning(f"纳指热点日报生成失败: {exc}")
            yield event.plain_result(f"热点日报生成失败: {exc}")
            return

        for chunk in self._chunk_text(report):
            yield event.plain_result(chunk)

    @filter.command("mh_push_now")
    async def push_now(self, event: AstrMessageEvent):
        """立即生成一份热点日报并推送到已绑定 QQ 群。"""
        if not self._is_admin_event(event):
            yield event.plain_result(self._permission_denied_message(event))
            return

        try:
            report = await self._generate_report()
            sent_count, failures = await self._broadcast_report(report)
        except Exception as exc:
            logger.warning(f"纳指热点日报手动推送失败: {exc}")
            yield event.plain_result(f"热点日报推送失败: {exc}")
            return

        if failures:
            yield event.plain_result(
                f"热点日报已推送到 {sent_count} 个群，失败 {len(failures)} 个。"
            )
            return
        yield event.plain_result(f"热点日报已推送到 {sent_count} 个群。")

    async def terminate(self):
        if self._daily_task:
            self._daily_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._daily_task
