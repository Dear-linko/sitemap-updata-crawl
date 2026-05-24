from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from monitor.types import HtmlReportConfig, TargetConfig, TelegramConfig


class RawTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    url: HttpUrl
    webhook_url: Optional[HttpUrl] = None
    enabled: bool = True


class RawHtmlReportConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    output_dir: str = Field(default="./docs", min_length=1)


class RawTelegramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None

    @field_validator("bot_token", "chat_id")
    @classmethod
    def _strip_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class RawConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval_minutes: int = Field(default=5, ge=1)
    request_timeout_sec: int = Field(default=15, ge=1)
    user_agent: str = Field(default="sitemap-monitor/1.0", min_length=1)
    targets: list[RawTarget] = Field(default_factory=list)
    html_report: RawHtmlReportConfig = Field(default_factory=RawHtmlReportConfig)
    telegram: RawTelegramConfig = Field(default_factory=RawTelegramConfig)


class AppConfig(BaseModel):
    interval_minutes: int
    request_timeout_sec: int
    user_agent: str
    targets: list[TargetConfig]
    html_report: HtmlReportConfig
    telegram: TelegramConfig


def _env_key_for_target(target_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", target_name).strip("_").upper()
    return f"SITEMAP_WEBHOOK_{safe}"


def _resolve_webhook(raw_target: RawTarget) -> Optional[str]:
    target_key = _env_key_for_target(raw_target.name)
    if os.getenv(target_key):
        return os.getenv(target_key)
    if os.getenv("SITEMAP_WEBHOOK_URL"):
        return os.getenv("SITEMAP_WEBHOOK_URL")
    if raw_target.webhook_url:
        return str(raw_target.webhook_url)
    return None


def _resolve_telegram_bot_token(raw: RawTelegramConfig) -> Optional[str]:
    env = os.getenv("TELEGRAM_BOT_TOKEN")
    if env and env.strip():
        return env.strip()
    return raw.bot_token


def _resolve_telegram_chat_id(raw: RawTelegramConfig) -> Optional[str]:
    env = os.getenv("TELEGRAM_CHAT_ID")
    if env and env.strip():
        return env.strip()
    return raw.chat_id


def load_config(path: str) -> AppConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with p.open("r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f) or {}

    raw = RawConfig.model_validate(raw_data)

    targets = [
        TargetConfig(
            name=t.name,
            url=str(t.url),
            webhook_url=_resolve_webhook(t),
            enabled=t.enabled,
        )
        for t in raw.targets
    ]

    return AppConfig(
        interval_minutes=raw.interval_minutes,
        request_timeout_sec=raw.request_timeout_sec,
        user_agent=raw.user_agent,
        targets=targets,
        html_report=HtmlReportConfig(
            enabled=raw.html_report.enabled,
            output_dir=raw.html_report.output_dir,
        ),
        telegram=TelegramConfig(
            enabled=raw.telegram.enabled,
            bot_token=_resolve_telegram_bot_token(raw.telegram),
            chat_id=_resolve_telegram_chat_id(raw.telegram),
        ),
    )
