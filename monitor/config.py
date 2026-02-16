from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from monitor.types import TargetConfig


class RawTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    url: HttpUrl
    webhook_url: Optional[HttpUrl] = None
    enabled: bool = True


class RawConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interval_minutes: int = Field(default=5, ge=1)
    request_timeout_sec: int = Field(default=15, ge=1)
    user_agent: str = Field(default="sitemap-monitor/1.0", min_length=1)
    targets: list[RawTarget] = Field(default_factory=list)


class AppConfig(BaseModel):
    interval_minutes: int
    request_timeout_sec: int
    user_agent: str
    targets: list[TargetConfig]


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
    )
