#!/bin/bash
# Sync sitemap monitor reports to public GitHub Pages
set -euo pipefail
shopt -s nullglob

REPO_DIR="$HOME/Projects/sitemap-updata-crawl-reports"
MONITOR_DIR="$HOME/Projects/sitemap-updata-crawl"
LOCK_DIR="${TMPDIR:-/tmp}/sitemap-updata-crawl.lock"

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [warn] sitemap sync already running; skipping"
    exit 0
fi

cleanup() {
    rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

push_with_retry() {
    local attempt=1
    local max_attempts=3
    local delay=30

    while true; do
        if git push "$PUSH_URL" main; then
            return 0
        fi

        if [ "$attempt" -ge "$max_attempts" ]; then
            echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] git push failed after ${max_attempts} attempts"
            return 1
        fi

        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [warn] git push failed, retrying in ${delay}s (attempt ${attempt}/${max_attempts})"
        sleep "$delay"
        attempt=$((attempt + 1))
        delay=$((delay * 2))
    done
}

cd "$MONITOR_DIR" || exit 1

# Run the monitor
source .venv/bin/activate
if python -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] monitor failed with exit code ${EXIT_CODE}"
    exit "$EXIT_CODE"
fi

# Rebuild the index and sync whatever is already local. This also retries
# reports commits left behind by an earlier network failure.
python -c "
from monitor.local_store import _render_html_index, _write_text
from pathlib import Path
output_root = Path('data/reports_html')
_write_text(output_root / 'index.html', _render_html_index(output_root))
"

if [ -f data/reports_html/index.html ]; then
    cp data/reports_html/index.html "$REPO_DIR/"
fi

daily_pages=(data/reports_html/daily/*.html)
if [ "${#daily_pages[@]}" -gt 0 ]; then
    cp "${daily_pages[@]}" "$REPO_DIR/daily/"
fi

# Commit and push (embed token in URL for cron/headless compatibility)
cd "$REPO_DIR"
GH_TOKEN=$(GH_CONFIG_DIR=~/.config/gh-file /Users/liike/.local/bin/gh auth token 2>/dev/null)
if [ -z "$GH_TOKEN" ]; then
    echo "[error] Failed to get GitHub token"
    exit 1
fi
PUSH_URL="https://Dear-linko:${GH_TOKEN}@github.com/Dear-linko/sitemap-updata-crawl-reports.git"
git add daily/ index.html
if ! git diff --cached --quiet; then
    git commit -m "Auto-update: $(date +%Y-%m-%d)"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] no report changes to commit"
fi
push_with_retry

exit $EXIT_CODE
