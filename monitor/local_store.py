from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def ensure_storage(baseline_path: str, reports_dir: str) -> None:
    baseline = Path(baseline_path)
    reports = Path(reports_dir)
    baseline.parent.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    if not baseline.exists():
        now = datetime.now(timezone.utc).isoformat()
        _write_json(
            baseline,
            {
                "meta": {"created_at": now, "updated_at": now},
                "targets": {},
            },
        )


def load_baseline(baseline_path: str) -> Dict[str, Any]:
    path = Path(baseline_path)
    if not path.exists():
        return {"meta": {}, "targets": {}}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {"meta": {}, "targets": {}}
    data.setdefault("meta", {})
    data.setdefault("targets", {})
    return data


def save_baseline(baseline_path: str, baseline: Dict[str, Any]) -> None:
    baseline.setdefault("meta", {})
    baseline["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
    baseline.setdefault("targets", {})
    _write_json(Path(baseline_path), baseline)


def append_daily_report(reports_dir: str, checked_at: str, run_report: Dict[str, Any]) -> Path:
    date_key = checked_at[:10]
    report_path = Path(reports_dir) / f"{date_key}.json"

    if report_path.exists():
        with report_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    else:
        data = []

    data.append(run_report)
    _write_json(report_path, data)
    return report_path


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def get_previous_urls(baseline: Dict[str, Any], target_name: str) -> Optional[List[str]]:
    target_row = baseline.get("targets", {}).get(target_name)
    if not isinstance(target_row, dict):
        return None
    urls = target_row.get("sitemap_urls")
    if not isinstance(urls, list):
        return None
    return [str(x) for x in urls]


def set_current_urls(
    baseline: Dict[str, Any],
    target_name: str,
    target_url: str,
    checked_at: str,
    sitemap_urls: List[str],
    http_status: Optional[int],
) -> None:
    targets = baseline.setdefault("targets", {})
    targets[target_name] = {
        "name": target_name,
        "url": target_url,
        "checked_at": checked_at,
        "http_status": http_status,
        "url_count": len(sitemap_urls),
        "sitemap_urls": sitemap_urls,
    }
