import json
from pathlib import Path

from monitor.local_store import (
    append_daily_report,
    ensure_storage,
    get_previous_urls,
    load_baseline,
    save_baseline,
    set_current_urls,
)


def test_local_store_baseline_and_daily_report(tmp_path: Path) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"

    ensure_storage(str(baseline_path), str(reports_dir))
    baseline = load_baseline(str(baseline_path))

    assert "targets" in baseline
    assert get_previous_urls(baseline, "main") is None

    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/a"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    baseline2 = load_baseline(str(baseline_path))
    prev = get_previous_urls(baseline2, "main")
    assert prev == ["https://example.com/a"]

    run_report = {
        "checked_at": "2026-02-16T00:10:00+00:00",
        "summary": {"processed": 1, "updated_targets": 1, "added_urls_total": 1, "errors": 0},
        "targets": [
            {
                "name": "main",
                "url": "https://example.com/sitemap.xml",
                "status": "updated",
                "reason": "urls_added",
                "http_status": 200,
                "url_count": 2,
                "added_count": 1,
                "added_urls": ["https://example.com/b"],
                "checked_at": "2026-02-16T00:10:00+00:00",
            }
        ],
    }
    report_path = append_daily_report(str(reports_dir), "2026-02-16T00:10:00+00:00", run_report)

    with report_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["summary"]["updated_targets"] == 1
