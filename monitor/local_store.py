from __future__ import annotations

import json
import re
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _ordered_unique(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


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


def append_daily_html_report(output_dir: str, checked_at: str, run_report: Dict[str, Any]) -> Path:
    date_key = checked_at[:10]
    output_root = Path(output_dir)
    html_path = output_root / "daily" / f"{date_key}.html"

    report_json_path = run_report.get("_report_json_path")
    daily_runs: List[Dict[str, Any]] = []
    if isinstance(report_json_path, str) and report_json_path:
        json_path = Path(report_json_path)
        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                daily_runs = [item for item in data if isinstance(item, dict)]

    if not daily_runs:
        daily_runs = [run_report]

    html = _render_daily_html(date_key=date_key, daily_runs=daily_runs)
    _write_text(html_path, html)
    _write_text(output_root / "index.html", _render_html_index(output_root))
    return html_path


def rebuild_html_reports(output_dir: str, reports_dir: str) -> int:
    output_root = Path(output_dir)
    daily_dir = output_root / "daily"
    reports_path = Path(reports_dir)
    daily_dir.mkdir(parents=True, exist_ok=True)

    for old_file in daily_dir.glob("*.html"):
        old_file.unlink()

    generated = 0
    for report_file in sorted(reports_path.glob("*.json")):
        with report_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            continue
        daily_runs = [item for item in data if isinstance(item, dict)]
        if not daily_runs:
            continue
        date_key = report_file.stem
        html = _render_daily_html(date_key=date_key, daily_runs=daily_runs)
        _write_text(daily_dir / f"{date_key}.html", html)
        generated += 1

    _write_text(output_root / "index.html", _render_html_index(output_root))
    return generated


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        f.write(text)
    tmp.replace(path)


def _render_daily_html(date_key: str, daily_runs: List[Dict[str, Any]]) -> str:
    run_count = len(daily_runs)
    last_checked_at = str(daily_runs[-1].get("checked_at", "-")) if daily_runs else "-"
    total_added_urls = sum(
        int(run.get("summary", {}).get("added_urls_total", 0))
        for run in daily_runs
        if isinstance(run, dict)
    )
    total_updated_targets = sum(
        int(run.get("summary", {}).get("updated_targets", 0))
        for run in daily_runs
        if isinstance(run, dict)
    )
    heading_pool = _ordered_unique(
        [
            str(item.get("heading")).strip()
            for run in daily_runs
            for target in run.get("targets", [])
            if isinstance(target, dict)
            for item in target.get("heading_results", [])
            if isinstance(item, dict)
            and item.get("ok") is True
            and isinstance(item.get("heading"), str)
            and str(item.get("heading")).strip()
        ]
    )
    trends_pool = _ordered_unique(
        [
            str(link).strip()
            for run in daily_runs
            for link in run.get("google-trends", [])
            if isinstance(link, str) and str(link).strip()
        ]
    )

    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        f"<meta name='report-date' content='{escape(date_key)}'>",
        f"<meta name='run-count' content='{run_count}'>",
        f"<meta name='total-added-urls' content='{total_added_urls}'>",
        f"<meta name='total-updated-targets' content='{total_updated_targets}'>",
        f"<meta name='last-checked-at' content='{escape(last_checked_at)}'>",
        f"<title>Sitemap Daily Report {escape(date_key)}</title>",
        (
            "<style>"
            ":root{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--card:#ffffff;--line:#e2e8f0;--head:#f1f5f9;}"
            "*{box-sizing:border-box;}"
            "body{font-family:'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;margin:0;line-height:1.55;background:var(--bg);color:var(--fg);}"
            ".container{max-width:940px;margin:0 auto;padding:24px 16px 48px;}"
            ".hero{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:16px;margin-bottom:12px;}"
            ".hero h1{margin:0;font-size:24px;line-height:1.2;letter-spacing:-.01em;}"
            ".hero p{margin:8px 0 0;color:var(--muted);font-size:14px;}"
            ".panel{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:12px;margin:0 0 12px;}"
            ".panel-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px;}"
            ".panel h2{margin:0;font-size:16px;}"
            ".btn{border:1px solid var(--line);background:#f8fafc;color:#334155;border-radius:8px;padding:6px 10px;font-size:12px;cursor:pointer;}"
            ".btn:hover{background:#eef2f7;}"
            ".chips{display:flex;flex-wrap:wrap;gap:6px;}"
            ".chip{display:inline-block;background:#f8fafc;color:#334155;border:1px solid var(--line);border-radius:999px;padding:3px 8px;font-size:12px;}"
            ".links{margin:0;padding:0;list-style:none;display:grid;gap:6px;}"
            ".links li{margin:0;}"
            ".link-item{display:block;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:#f8fafc;word-break:break-all;overflow-wrap:anywhere;}"
            ".link-item:hover{background:#f1f5f9;}"
            ".section{border:1px solid var(--line);border-radius:10px;background:var(--card);padding:12px;margin:0 0 12px;}"
            ".section h2{margin:0 0 8px;font-size:16px;}"
            "table{width:100%;border-collapse:collapse;table-layout:fixed;}"
            "th,td{border:1px solid var(--line);padding:8px;vertical-align:top;text-align:left;font-size:13px;word-break:break-word;overflow-wrap:anywhere;}"
            "th{background:var(--head);font-weight:600;}"
            "a{color:var(--fg);text-decoration:none;word-break:break-word;overflow-wrap:anywhere;}"
            "a:hover{text-decoration:underline;}"
            "code{background:#f8fafc;border:1px solid var(--line);padding:1px 5px;border-radius:6px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;}"
            ".muted{color:var(--muted);font-size:12px;}"
            "@media (max-width:640px){"
            ".container{padding:14px 10px 28px;}"
            ".hero{padding:12px;border-radius:10px;margin-bottom:10px;}"
            ".hero h1{font-size:20px;}"
            ".hero p{font-size:13px;}"
            ".panel,.section{padding:10px;}"
            ".panel-head{display:block;}"
            ".btn{margin-top:8px;width:100%;}"
            "table,thead,tbody,tr,th,td{display:block;width:100%;}"
            "thead{display:none;}"
            "tr{border:1px solid var(--line);margin-bottom:8px;padding:6px;background:#fff;}"
            "td{border:none;padding:4px 2px;font-size:12px;}"
            "code{font-size:11px;}"
            "}"
            "</style>"
        ),
        "</head>",
        "<body>",
        "<div class='container'>",
        "<div class='hero'>",
        f"<h1>Sitemap Daily Report - {escape(date_key)}</h1>",
        "<p>Headings and trends first, then categorized detail tables.</p>",
        "</div>",
        "<section class='panel'>",
        "<div class='panel-head'>",
        "<h2>Heading Collection</h2>",
        "<button id='copy-headings' class='btn' type='button'>Copy All Headings</button>",
        "</div>",
        "<div class='chips'>",
    ]
    if heading_pool:
        for heading in heading_pool:
            parts.append(f"<span class='chip'>{escape(heading)}</span>")
    else:
        parts.append("<span class='chip'>None</span>")
    parts.extend(
        [
            "</div>",
            f"<textarea id='heading-copy-src' style='position:absolute;left:-9999px;top:-9999px;'>{escape(','.join(heading_pool))}</textarea>",
            "</section>",
            "<section class='panel'>",
            "<h2>Trends Link Collection</h2>",
            "<ul class='links'>",
        ]
    )
    if trends_pool:
        for link in trends_pool:
            safe_link = escape(link)
            parts.append(
                f"<li><a class='link-item' href='{safe_link}' target='_blank' rel='noopener noreferrer'>{safe_link}</a></li>"
            )
    else:
        parts.append("<li>None</li>")
    parts.extend(["</ul>", "</section>"])

    parts.extend(
        [
            "<section class='section'>",
            "<h2>Heading Results</h2>",
            "<table>",
            "<thead><tr><th>Target</th><th>URL</th><th>Heading</th><th>Tag</th><th>Reason</th></tr></thead>",
            "<tbody>",
        ]
    )
    heading_any = False
    for run in daily_runs:
        for target in run.get("targets", []):
            if not isinstance(target, dict):
                continue
            target_name = escape(str(target.get("name", "-")))
            for item in target.get("heading_results", []):
                if not isinstance(item, dict):
                    continue
                url = escape(str(item.get("url", "-")))
                heading = escape(str(item.get("heading", "-")))
                tag = escape(str(item.get("heading_tag", "-")))
                reason = escape(str(item.get("reason", "-")))
                parts.append(
                    "<tr>"
                    f"<td>{target_name}</td>"
                    f"<td><a href='{url}' target='_blank' rel='noopener noreferrer'>{url}</a></td>"
                    f"<td><code>{heading}</code></td>"
                    f"<td><code>{tag}</code></td>"
                    f"<td><code>{reason}</code></td>"
                    "</tr>"
                )
                heading_any = True
    if not heading_any:
        parts.append("<tr><td colspan='5'>None</td></tr>")
    parts.extend(["</tbody>", "</table>", "</section>"])
    parts.extend(
        [
            "<script>",
            "(function(){",
            "var btn=document.getElementById('copy-headings');",
            "var src=document.getElementById('heading-copy-src');",
            "if(!btn||!src){return;}",
            "btn.addEventListener('click', function(){",
            "var text=src.value||'';",
            "if(!text){btn.textContent='No Heading';setTimeout(function(){btn.textContent='Copy All Headings';},1200);return;}",
            "if(navigator.clipboard&&navigator.clipboard.writeText){",
            "navigator.clipboard.writeText(text).then(function(){btn.textContent='Copied';setTimeout(function(){btn.textContent='Copy All Headings';},1200);}).catch(function(){fallback();});",
            "}else{fallback();}",
            "function fallback(){src.focus();src.select();try{document.execCommand('copy');btn.textContent='Copied';}catch(e){btn.textContent='Copy Failed';}setTimeout(function(){btn.textContent='Copy All Headings';},1200);}",
            "});",
            "})();",
            "</script>",
            "</div></body></html>",
        ]
    )
    return "\n".join(parts)


def _render_html_index(output_root: Path) -> str:
    daily_dir = output_root / "daily"
    daily_files = sorted(daily_dir.glob("*.html"), key=lambda p: p.name, reverse=True)

    parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width, initial-scale=1'>",
        "<title>Sitemap HTML Reports</title>",
        (
            "<style>"
            ":root{--bg:#f8fafc;--fg:#0f172a;--muted:#64748b;--card:#ffffff;--line:#e2e8f0;}"
            "*{box-sizing:border-box;}"
            "body{font-family:'Inter','Segoe UI',-apple-system,BlinkMacSystemFont,sans-serif;margin:0;background:var(--bg);color:var(--fg);}"
            ".container{max-width:940px;margin:0 auto;padding:24px 16px 48px;}"
            ".hero{border:1px solid var(--line);border-radius:12px;background:var(--card);padding:16px;margin-bottom:12px;}"
            ".hero h1{margin:0;font-size:24px;line-height:1.2;letter-spacing:-.01em;}"
            ".hero p{margin:8px 0 0;color:var(--muted);font-size:14px;}"
            ".list{list-style:none;margin:0;padding:0;display:grid;gap:8px;}"
            ".item{background:var(--card);border:1px solid var(--line);border-radius:10px;}"
            "a{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;padding:12px;color:var(--fg);text-decoration:none;}"
            "a:hover{background:#f8fafc;}"
            ".left{min-width:210px;max-width:42%;}"
            ".title{font-weight:700;font-size:16px;line-height:1.2;}"
            ".muted{margin-top:6px;color:var(--muted);font-size:12px;}"
            ".right{display:flex;flex-wrap:wrap;gap:6px;justify-content:flex-end;align-items:center;}"
            ".tag{font-size:12px;background:#f8fafc;border:1px solid var(--line);border-radius:999px;padding:3px 8px;color:#334155;font-weight:600;}"
            ".foot{margin:12px 0 0;color:var(--muted);font-size:13px;}"
            "@media (max-width:640px){"
            ".container{padding:14px 10px 28px;}"
            ".hero{padding:12px;border-radius:10px;margin-bottom:10px;}"
            ".hero h1{font-size:20px;}"
            ".hero p{font-size:13px;}"
            "a{padding:10px;display:block;}"
            ".left{max-width:none;min-width:0;}"
            ".right{justify-content:flex-start;margin-top:8px;}"
            ".title{font-size:14px;}"
            ".tag{font-size:11px;padding:2px 7px;}"
            ".muted{margin-top:5px;font-size:12px;}"
            ".foot{margin-top:10px;font-size:12px;}"
            "}"
            "</style>"
        ),
        "</head>",
        "<body>",
        "<div class='container'>",
        "<div class='hero'><h1>Sitemap HTML Reports</h1><p>Open any daily report below.</p></div>",
        "<ul class='list'>",
    ]
    if daily_files:
        for path in daily_files:
            name = escape(path.stem)
            href = escape(f"daily/{path.name}")
            html = path.read_text(encoding="utf-8", errors="ignore")
            run_count = _safe_int(_extract_meta(html, "run-count"))
            total_added = _safe_int(_extract_meta(html, "total-added-urls"))
            updated_targets = _safe_int(_extract_meta(html, "total-updated-targets"))
            last_checked = escape(_extract_meta(html, "last-checked-at") or "-")
            parts.append("<li class='item'>")
            parts.append(f"<a href='{href}'>")
            parts.append("<div class='left'>")
            parts.append(f"<div class='title'>{name}</div>")
            parts.append(f"<div class='muted'>last checked: {last_checked}</div>")
            parts.append("</div>")
            parts.append("<div class='right'>")
            parts.append(f"<span class='tag'>runs {run_count}</span>")
            parts.append(f"<span class='tag'>added {total_added}</span>")
            parts.append(f"<span class='tag'>targets {updated_targets}</span>")
            parts.append("</div>")
            parts.append("</a>")
            parts.append("</li>")
    else:
        parts.append("<li class='item'><a href='#'>No daily reports yet.</a></li>")
    parts.extend(["</ul>", "<p class='foot'>Generated by sitemap-monitor.</p>", "</div>", "</body></html>"])
    return "\n".join(parts)


def _extract_meta(html: str, name: str) -> Optional[str]:
    pattern = rf"<meta\s+name=['\"]{re.escape(name)}['\"]\s+content=['\"]([^'\"]*)['\"]"
    m = re.search(pattern, html)
    if not m:
        return None
    return m.group(1).strip()


def _safe_int(value: Optional[str]) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0


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
