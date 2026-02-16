from __future__ import annotations

import argparse
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from monitor.config import load_config
from monitor.fetcher import SitemapFetcher
from monitor.heading_parser import extract_heading
from monitor.local_store import (
    append_daily_report,
    ensure_storage,
    get_previous_urls,
    load_baseline,
    save_baseline,
    set_current_urls,
)
from monitor.logging_setup import setup_logging
from monitor.notifier import WebhookNotifier
from monitor.sitemap_parser import extract_sitemap_urls
from monitor.types import NotifyPayload

LOGGER = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ordered_unique(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _google_trends_links(keywords: List[str], batch_size: int = 5) -> List[str]:
    if batch_size <= 0:
        return []
    links: List[str] = []
    for i in range(0, len(keywords), batch_size):
        batch = keywords[i : i + batch_size]
        if not batch:
            continue
        encoded_keywords = ",".join(urllib.parse.quote(keyword, safe="") for keyword in batch)
        links.append(f"https://trends.google.com/trends/explore?date=today%201-m&q={encoded_keywords}")
    return links


def cmd_init_state(args: argparse.Namespace) -> int:
    setup_logging(args.log_level)
    ensure_storage(args.baseline, args.reports_dir)
    LOGGER.info("Storage initialized: baseline=%s reports_dir=%s", args.baseline, args.reports_dir)
    return 0


def cmd_test_notify(args: argparse.Namespace) -> int:
    setup_logging(args.log_level)
    config = load_config(args.config)
    target = next((t for t in config.targets if t.name == args.target), None)
    if target is None:
        LOGGER.error("Target not found: %s", args.target)
        return 1
    if not target.webhook_url:
        LOGGER.error("No webhook configured for target: %s", args.target)
        return 1

    notifier = WebhookNotifier(timeout_sec=config.request_timeout_sec)
    try:
        payload = NotifyPayload(
            target_name=target.name,
            url=target.url,
            checked_at=_now_iso(),
            reason="manual_test",
            changed_fields=["manual"],
            old={"etag": "-", "last_modified": "-", "content_hash": "-"},
            new={"etag": "-", "last_modified": "-", "content_hash": "-"},
        )
        ok = notifier.send(target.webhook_url, payload)
        if ok:
            LOGGER.info("Test notification sent for target: %s", target.name)
            return 0
        LOGGER.error("Test notification failed for target: %s", target.name)
        return 1
    finally:
        notifier.close()


def _process_target(
    fetcher: SitemapFetcher,
    baseline: Dict[str, Any],
    target_name: str,
    target_url: str,
    checked_at: str,
) -> Dict[str, Any]:
    content = fetcher.fetch_content_hash(target_url)

    if content.error or content.content_bytes is None:
        LOGGER.error("Check failed for %s: %s", target_url, content.error or "content_fetch_failed")
        return {
            "name": target_name,
            "url": target_url,
            "status": "error",
            "reason": "content_fetch_failed",
            "http_status": content.http_status,
            "url_count": 0,
            "added_count": 0,
            "added_urls": [],
            "checked_at": checked_at,
        }

    current_urls = extract_sitemap_urls(content.content_bytes, target_url)
    previous_urls = get_previous_urls(baseline, target_name)

    if previous_urls is None:
        status = "baseline"
        reason = "initial_baseline"
        added_urls: List[str] = []
    else:
        prev_set = set(previous_urls)
        added_urls = sorted([u for u in current_urls if u not in prev_set])
        status = "updated" if added_urls else "unchanged"
        reason = "urls_added" if added_urls else "no_new_urls"

    set_current_urls(
        baseline=baseline,
        target_name=target_name,
        target_url=target_url,
        checked_at=checked_at,
        sitemap_urls=current_urls,
        http_status=content.http_status,
    )

    heading_results: List[Dict[str, Any]] = []
    for added_url in added_urls:
        page = fetcher.fetch_page(added_url)
        if page.error or page.content_bytes is None:
            heading_results.append(
                {
                    "url": added_url,
                    "http_status": page.http_status,
                    "heading": None,
                    "heading_tag": None,
                    "ok": False,
                    "reason": "fetch_failed",
                }
            )
            continue

        heading, heading_tag, reason = extract_heading(page.content_bytes)
        heading_results.append(
            {
                "url": added_url,
                "http_status": page.http_status,
                "heading": heading,
                "heading_tag": heading_tag,
                "ok": reason in {"ok_h1", "ok_h2"},
                "reason": reason,
            }
        )

    target_keywords = _ordered_unique(
        [
            str(item.get("heading")).strip()
            for item in heading_results
            if item.get("ok") is True and isinstance(item.get("heading"), str) and str(item.get("heading")).strip()
        ]
    )

    return {
        "name": target_name,
        "url": target_url,
        "status": status,
        "reason": reason,
        "http_status": content.http_status,
        "url_count": len(current_urls),
        "added_count": len(added_urls),
        "added_urls": added_urls,
        "heading_results": heading_results,
        "keywords": {"keywords": target_keywords},
        "checked_at": checked_at,
    }


def cmd_run_once(args: argparse.Namespace) -> int:
    setup_logging(args.log_level)
    config = load_config(args.config)
    ensure_storage(args.baseline, args.reports_dir)

    checked_at = _now_iso()
    baseline = load_baseline(args.baseline)
    enabled_targets = [t for t in config.targets if t.enabled]
    if not enabled_targets:
        LOGGER.warning("No enabled targets found in config")
        return 0

    fetcher = SitemapFetcher(timeout_sec=config.request_timeout_sec, user_agent=config.user_agent)
    try:
        target_reports: List[Dict[str, Any]] = []
        for target in enabled_targets:
            target_reports.append(
                _process_target(
                    fetcher=fetcher,
                    baseline=baseline,
                    target_name=target.name,
                    target_url=target.url,
                    checked_at=checked_at,
                )
            )
    finally:
        fetcher.close()

    save_baseline(args.baseline, baseline)

    updated_targets = [r for r in target_reports if r["added_count"] > 0]
    added_urls_total = sum(r["added_count"] for r in updated_targets)
    errors = sum(1 for r in target_reports if r["status"] == "error")
    heading_ok_total = sum(
        1
        for target in updated_targets
        for item in target.get("heading_results", [])
        if item.get("ok") is True
    )
    heading_failed_total = sum(
        1
        for target in updated_targets
        for item in target.get("heading_results", [])
        if item.get("ok") is False
    )
    global_keywords = _ordered_unique(
        [
            keyword
            for target in updated_targets
            for keyword in target.get("keywords", {}).get("keywords", [])
            if isinstance(keyword, str) and keyword.strip()
        ]
    )

    if updated_targets:
        trends_links = _google_trends_links(global_keywords, batch_size=5)
        run_report = {
            "checked_at": checked_at,
            "summary": {
                "processed": len(target_reports),
                "updated_targets": len(updated_targets),
                "added_urls_total": added_urls_total,
                "errors": errors,
                "heading_ok_total": heading_ok_total,
                "heading_failed_total": heading_failed_total,
            },
            "keywords": {"keywords": global_keywords},
            "google-trends": trends_links,
            "targets": updated_targets,
        }
        report_path = append_daily_report(args.reports_dir, checked_at, run_report)
        LOGGER.info(
            "Run done: processed=%s updated_targets=%s added_urls_total=%s report=%s",
            len(target_reports),
            len(updated_targets),
            added_urls_total,
            report_path,
        )
    else:
        LOGGER.info(
            "Run done: processed=%s updated_targets=0 added_urls_total=0 errors=%s; report skipped",
            len(target_reports),
            errors,
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sitemap new-URL monitor")
    parser.add_argument("--log-level", default="INFO", help="Log level, e.g. INFO/DEBUG")

    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once = subparsers.add_parser("run-once", help="Run one monitoring cycle")
    run_once.add_argument("--config", required=True, help="Path to config YAML")
    run_once.add_argument("--baseline", default="./data/baseline.json", help="Baseline JSON path")
    run_once.add_argument("--reports-dir", default="./data/reports", help="Daily reports directory")
    run_once.set_defaults(func=cmd_run_once)

    init_state = subparsers.add_parser("init-state", help="Initialize baseline file and reports directory")
    init_state.add_argument("--baseline", default="./data/baseline.json", help="Baseline JSON path")
    init_state.add_argument("--reports-dir", default="./data/reports", help="Daily reports directory")
    init_state.set_defaults(func=cmd_init_state)

    # Backward-compatible alias
    init_db = subparsers.add_parser("init-db", help="Alias of init-state")
    init_db.add_argument("--baseline", default="./data/baseline.json", help="Baseline JSON path")
    init_db.add_argument("--reports-dir", default="./data/reports", help="Daily reports directory")
    init_db.set_defaults(func=cmd_init_state)

    test_notify = subparsers.add_parser("test-notify", help="Send test notification")
    test_notify.add_argument("--config", required=True, help="Path to config YAML")
    test_notify.add_argument("--target", required=True, help="Target name")
    test_notify.set_defaults(func=cmd_test_notify)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
