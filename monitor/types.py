from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class TargetConfig:
    name: str
    url: str
    webhook_url: Optional[str]
    enabled: bool = True


@dataclass(frozen=True)
class HtmlReportConfig:
    enabled: bool = False
    output_dir: str = "./docs"


@dataclass(frozen=True)
class TelegramConfig:
    enabled: bool = False
    bot_token: Optional[str] = None
    chat_id: Optional[str] = None


@dataclass
class FetchResult:
    etag: Optional[str] = None
    last_modified: Optional[str] = None
    content_hash: Optional[str] = None
    http_status: Optional[int] = None
    error: Optional[str] = None
    content_bytes: Optional[bytes] = None


@dataclass
class CheckState:
    name: str
    url: str
    etag: Optional[str]
    last_modified: Optional[str]
    content_hash: Optional[str]
    sitemap_urls: Optional[List[str]]
    status: str
    checked_at: str


@dataclass
class CheckDecision:
    updated: bool
    reason: str
    changed_fields: list[str] = field(default_factory=list)
    should_fetch_content: bool = False
    event_type: str = "unchanged"


@dataclass(frozen=True)
class NotifyPayload:
    target_name: str
    url: str
    checked_at: str
    reason: str
    changed_fields: list[str]
    old: dict[str, Any]
    new: dict[str, Any]

    def to_wecom(self) -> dict[str, Any]:
        old_etag = self.old.get("etag") or "-"
        new_etag = self.new.get("etag") or "-"
        old_last_modified = self.old.get("last_modified") or "-"
        new_last_modified = self.new.get("last_modified") or "-"
        old_hash = self.old.get("content_hash") or "-"
        new_hash = self.new.get("content_hash") or "-"

        lines = [
            "Sitemap updated",
            f"Target: {self.target_name}",
            f"URL: {self.url}",
            f"Time: {self.checked_at}",
            f"Reason: {self.reason}",
            f"Changed: {', '.join(self.changed_fields) if self.changed_fields else '-'}",
            f"ETag: {old_etag} -> {new_etag}",
            f"Last-Modified: {old_last_modified} -> {new_last_modified}",
            f"Hash: {old_hash} -> {new_hash}",
        ]
        return {"msgtype": "text", "text": {"content": "\n".join(lines)}}

    def to_feishu(self) -> dict[str, Any]:
        old_etag = self.old.get("etag") or "-"
        new_etag = self.new.get("etag") or "-"
        old_last_modified = self.old.get("last_modified") or "-"
        new_last_modified = self.new.get("last_modified") or "-"
        old_hash = self.old.get("content_hash") or "-"
        new_hash = self.new.get("content_hash") or "-"

        lines = [
            "Sitemap updated",
            f"Target: {self.target_name}",
            f"URL: {self.url}",
            f"Time: {self.checked_at}",
            f"Reason: {self.reason}",
            f"Changed: {', '.join(self.changed_fields) if self.changed_fields else '-'}",
            f"ETag: {old_etag} -> {new_etag}",
            f"Last-Modified: {old_last_modified} -> {new_last_modified}",
            f"Hash: {old_hash} -> {new_hash}",
        ]
        return {"msg_type": "text", "content": {"text": "\n".join(lines)}}
