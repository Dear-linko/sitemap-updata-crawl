import json
from pathlib import Path

from monitor.local_store import (
    append_daily_html_report,
    append_daily_report,
    ensure_storage,
    get_previous_urls,
    load_baseline,
    rebuild_html_reports,
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


def test_append_daily_html_report_renders_from_daily_json(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    html_dir = tmp_path / "reports_html"
    reports_dir.mkdir(parents=True, exist_ok=True)

    run_report = {
        "checked_at": "2026-02-16T00:10:00+00:00",
        "summary": {
            "processed": 1,
            "updated_targets": 1,
            "added_urls_total": 1,
            "heading_ok_total": 1,
            "heading_failed_total": 0,
        },
        "google-trends": ["https://trends.google.com/trends/explore?date=today%201-m&q=Title"],
        "targets": [
            {
                "name": "main",
                "url": "https://example.com/sitemap.xml",
                "added_urls": ["https://example.com/new"],
                "heading_results": [
                    {
                        "url": "https://example.com/new",
                        "heading": "Title",
                        "heading_tag": "h1",
                        "reason": "ok_h1",
                    }
                ],
            }
        ],
    }
    report_path = append_daily_report(str(reports_dir), "2026-02-16T00:10:00+00:00", run_report)
    run_report["_report_json_path"] = str(report_path)

    html_path = append_daily_html_report(str(html_dir), "2026-02-16T00:10:00+00:00", run_report)
    html = html_path.read_text(encoding="utf-8")
    index_html = (html_dir / "index.html").read_text(encoding="utf-8")

    assert html_path.name == "2026-02-16.html"
    assert html_path.parent.name == "daily"
    assert "Sitemap Daily Report - 2026-02-16" in html
    assert "https://example.com/new" in html
    assert "https://trends.google.com/trends/explore?" in html
    assert "daily/2026-02-16.html" in index_html


def test_rebuild_html_reports_from_json_files(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    html_dir = tmp_path / "reports_html"
    daily_dir = html_dir / "daily"
    reports_dir.mkdir(parents=True, exist_ok=True)
    daily_dir.mkdir(parents=True, exist_ok=True)
    (daily_dir / "stale.html").write_text("old", encoding="utf-8")

    report_a = [
        {
            "checked_at": "2026-02-16T00:10:00+00:00",
            "summary": {"processed": 1, "updated_targets": 1, "added_urls_total": 1, "heading_ok_total": 1, "heading_failed_total": 0},
            "google-trends": ["https://trends.google.com/trends/explore?date=today%201-m&q=A"],
            "targets": [
                {
                    "name": "main",
                    "url": "https://example.com/sitemap.xml",
                    "added_urls": ["https://example.com/a"],
                    "heading_results": [{"url": "https://example.com/a", "heading": "A", "heading_tag": "h1", "ok": True, "reason": "ok_h1"}],
                }
            ],
        }
    ]
    report_b = [
        {
            "checked_at": "2026-02-17T00:20:00+00:00",
            "summary": {"processed": 1, "updated_targets": 1, "added_urls_total": 1, "heading_ok_total": 1, "heading_failed_total": 0},
            "google-trends": ["https://trends.google.com/trends/explore?date=today%201-m&q=B"],
            "targets": [
                {
                    "name": "main",
                    "url": "https://example.com/sitemap.xml",
                    "added_urls": ["https://example.com/b"],
                    "heading_results": [{"url": "https://example.com/b", "heading": "B", "heading_tag": "h2", "ok": True, "reason": "ok_h2"}],
                }
            ],
        }
    ]
    (reports_dir / "2026-02-16.json").write_text(json.dumps(report_a), encoding="utf-8")
    (reports_dir / "2026-02-17.json").write_text(json.dumps(report_b), encoding="utf-8")

    generated = rebuild_html_reports(str(html_dir), str(reports_dir))

    assert generated == 2
    assert (daily_dir / "stale.html").exists() is False
    assert (daily_dir / "2026-02-16.html").exists() is True
    assert (daily_dir / "2026-02-17.html").exists() is True
    index_html = (html_dir / "index.html").read_text(encoding="utf-8")
    assert "daily/2026-02-16.html" in index_html
    assert "daily/2026-02-17.html" in index_html
