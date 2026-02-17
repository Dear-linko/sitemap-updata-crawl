import argparse
import json
from pathlib import Path
from typing import Optional

from monitor import cli
from monitor.local_store import ensure_storage, load_baseline, save_baseline, set_current_urls
from monitor.types import FetchResult, HtmlReportConfig, TargetConfig, TelegramConfig


class _DummyConfig:
    def __init__(
        self,
        targets,
        html_report: Optional[HtmlReportConfig] = None,
        telegram: Optional[TelegramConfig] = None,
    ):
        self.request_timeout_sec = 5
        self.user_agent = "test-agent"
        self.targets = targets
        self.html_report = html_report or HtmlReportConfig(enabled=False, output_dir="./unused")
        self.telegram = telegram or TelegramConfig(enabled=False, bot_token=None, chat_id=None)


def test_run_once_writes_heading_results_for_added_urls(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig([target])

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/new</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            assert url == "https://example.com/new"
            return FetchResult(http_status=200, content_bytes=b"<html><body><h2>New H2 Title</h2></body></html>")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    report_files = list(reports_dir.glob("*.json"))
    assert len(report_files) == 1

    data = json.loads(report_files[0].read_text(encoding="utf-8"))
    assert isinstance(data, list)
    last = data[-1]
    assert last["summary"]["updated_targets"] == 1
    assert last["summary"]["heading_ok_total"] == 1
    assert last["summary"]["heading_failed_total"] == 0
    assert last["keywords"] == {"keywords": ["New H2 Title"]}
    assert "google-trends" in last
    assert isinstance(last["google-trends"], list)
    assert len(last["google-trends"]) == 1
    assert last["google-trends"][0].startswith("https://trends.google.com/trends/explore?")

    target_row = last["targets"][0]
    assert target_row["added_count"] == 1
    assert len(target_row["heading_results"]) == 1
    assert target_row["keywords"] == {"keywords": ["New H2 Title"]}
    heading_item = target_row["heading_results"][0]
    assert heading_item["url"] == "https://example.com/new"
    assert heading_item["heading"] == "New H2 Title"
    assert heading_item["heading_tag"] == "h2"
    assert heading_item["ok"] is True
    assert heading_item["reason"] == "ok_h2"


def test_run_once_skips_report_when_no_updates(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig([target])

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            raise AssertionError("fetch_page should not be called when no added urls")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    report_files = list(reports_dir.glob("*.json"))
    assert report_files == []


def test_run_once_target_keywords_deduplicated(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig([target])

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/a</loc></url>
<url><loc>https://example.com/b</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            if url.endswith("/a"):
                return FetchResult(http_status=200, content_bytes=b"<html><h1>Same</h1></html>")
            return FetchResult(http_status=200, content_bytes=b"<html><h2>Same</h2></html>")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    data = json.loads(next(reports_dir.glob("*.json")).read_text(encoding="utf-8"))
    last = data[-1]
    assert last["targets"][0]["keywords"] == {"keywords": ["Same"]}
    assert last["keywords"] == {"keywords": ["Same"]}
    assert len(last["google-trends"]) == 1


def test_google_trends_links_batched_by_five(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=[],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig([target])

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/1</loc></url>
<url><loc>https://example.com/2</loc></url>
<url><loc>https://example.com/3</loc></url>
<url><loc>https://example.com/4</loc></url>
<url><loc>https://example.com/5</loc></url>
<url><loc>https://example.com/6</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            suffix = url.rsplit("/", 1)[-1]
            return FetchResult(http_status=200, content_bytes=f"<html><h1>K{suffix}</h1></html>".encode("utf-8"))

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    data = json.loads(next(reports_dir.glob("*.json")).read_text(encoding="utf-8"))
    last = data[-1]
    assert last["keywords"] == {"keywords": ["K1", "K2", "K3", "K4", "K5", "K6"]}
    assert len(last["google-trends"]) == 2


def test_run_once_global_keywords_deduplicated_across_targets(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="a",
        target_url="https://example.com/a.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=[],
        http_status=200,
    )
    set_current_urls(
        baseline=baseline,
        target_name="b",
        target_url="https://example.com/b.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=[],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    targets = [
        TargetConfig(name="a", url="https://example.com/a.xml", webhook_url=None, enabled=True),
        TargetConfig(name="b", url="https://example.com/b.xml", webhook_url=None, enabled=True),
    ]

    def fake_load_config(path: str):
        return _DummyConfig(targets)

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            if url.endswith("/a.xml"):
                xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/a1</loc></url>
</urlset>"""
            else:
                xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/b1</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            if url.endswith("a1"):
                return FetchResult(http_status=200, content_bytes=b"<html><h1>Shared</h1></html>")
            return FetchResult(http_status=200, content_bytes=b"<html><h1>Shared</h1><h2>Ignored</h2></html>")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    data = json.loads(next(reports_dir.glob("*.json")).read_text(encoding="utf-8"))
    last = data[-1]
    assert last["keywords"] == {"keywords": ["Shared"]}


def test_run_once_keywords_empty_when_all_heading_extraction_fails(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=[],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig([target])

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/new</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            return FetchResult(http_status=200, content_bytes=b"<html><p>none</p></html>")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    data = json.loads(next(reports_dir.glob("*.json")).read_text(encoding="utf-8"))
    last = data[-1]
    assert last["targets"][0]["keywords"] == {"keywords": []}
    assert last["keywords"] == {"keywords": []}


def test_run_once_writes_daily_html_report_when_enabled(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    html_dir = tmp_path / "reports_html"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig(
            [target],
            html_report=HtmlReportConfig(enabled=True, output_dir=str(html_dir)),
        )

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/new</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            return FetchResult(http_status=200, content_bytes=b"<html><h1>HTML Title</h1></html>")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0

    html = next((html_dir / "daily").glob("*.html")).read_text(encoding="utf-8")
    index_html = (html_dir / "index.html").read_text(encoding="utf-8")
    assert "HTML Title" in html
    assert "https://trends.google.com/trends/explore?" in html
    assert "daily/" in index_html


def test_run_once_daily_html_report_contains_multiple_runs_same_day(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    html_dir = tmp_path / "reports_html"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig(
            [target],
            html_report=HtmlReportConfig(enabled=True, output_dir=str(html_dir)),
        )

    class FakeFetcher:
        run_count = 0

        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            if FakeFetcher.run_count == 0:
                xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/new-1</loc></url>
</urlset>"""
            else:
                xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/new-1</loc></url>
<url><loc>https://example.com/new-2</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            if url.endswith("new-1"):
                return FetchResult(http_status=200, content_bytes=b"<html><h1>T1</h1></html>")
            return FetchResult(http_status=200, content_bytes=b"<html><h1>T2</h1></html>")

        def close(self) -> None:
            FakeFetcher.run_count += 1
            return

    times = iter(["2026-02-16T10:00:00+00:00", "2026-02-16T11:00:00+00:00"])
    monkeypatch.setattr(cli, "_now_iso", lambda: next(times))
    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    assert cli.cmd_run_once(args) == 0
    assert cli.cmd_run_once(args) == 0

    html = next((html_dir / "daily").glob("*.html")).read_text(encoding="utf-8")
    index_html = (html_dir / "index.html").read_text(encoding="utf-8")
    assert "meta name='run-count' content='2'" in html
    assert "https://example.com/new-1" in html
    assert "https://example.com/new-2" in html
    assert "daily/2026-02-16.html" in index_html


def test_run_once_telegram_enabled_but_missing_credentials_skips_send(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/old"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig(
            [target],
            telegram=TelegramConfig(enabled=True, bot_token=None, chat_id=None),
        )

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/old</loc></url>
<url><loc>https://example.com/new</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            return FetchResult(http_status=200, content_bytes=b"<html><h1>T</h1></html>")

        def close(self) -> None:
            return

    class FakeNotifier:
        send_calls = 0

        def __init__(self, timeout_sec: int):
            pass

        def send_telegram(self, bot_token: str, chat_id: str, text: str) -> bool:
            FakeNotifier.send_calls += 1
            return True

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)
    monkeypatch.setattr(cli, "WebhookNotifier", FakeNotifier)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    rc = cli.cmd_run_once(args)
    assert rc == 0
    assert FakeNotifier.send_calls == 0


def test_run_once_no_updates_does_not_write_html(tmp_path: Path, monkeypatch) -> None:
    baseline_path = tmp_path / "baseline.json"
    reports_dir = tmp_path / "reports"
    html_dir = tmp_path / "reports_html"
    ensure_storage(str(baseline_path), str(reports_dir))

    baseline = load_baseline(str(baseline_path))
    set_current_urls(
        baseline=baseline,
        target_name="main",
        target_url="https://example.com/sitemap.xml",
        checked_at="2026-02-16T00:00:00+00:00",
        sitemap_urls=["https://example.com/same"],
        http_status=200,
    )
    save_baseline(str(baseline_path), baseline)

    target = TargetConfig(name="main", url="https://example.com/sitemap.xml", webhook_url=None, enabled=True)

    def fake_load_config(path: str):
        return _DummyConfig(
            [target],
            html_report=HtmlReportConfig(enabled=True, output_dir=str(html_dir)),
        )

    class FakeFetcher:
        def __init__(self, timeout_sec: int, user_agent: str):
            pass

        def fetch_content_hash(self, url: str) -> FetchResult:
            xml = b"""<urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
<url><loc>https://example.com/same</loc></url>
</urlset>"""
            return FetchResult(http_status=200, content_bytes=xml, content_hash="abc")

        def fetch_page(self, url: str) -> FetchResult:
            raise AssertionError("fetch_page should not be called")

        def close(self) -> None:
            return

    monkeypatch.setattr(cli, "load_config", fake_load_config)
    monkeypatch.setattr(cli, "SitemapFetcher", FakeFetcher)

    args = argparse.Namespace(
        config="unused.yaml",
        baseline=str(baseline_path),
        reports_dir=str(reports_dir),
        log_level="INFO",
    )
    assert cli.cmd_run_once(args) == 0
    assert list(html_dir.glob("*.html")) == []
