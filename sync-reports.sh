#!/bin/bash
# Run the sitemap monitor and publish HTML reports to GitHub Pages.
#
# The published site lives on the orphan `gh-pages` branch of this same repo,
# checked out as a git worktree at ./.gh-pages (gitignored). The monitor writes
# HTML directly into that worktree; we then commit and push only the gh-pages
# branch, so the daily auto-commits never touch `main`.
#
# Pages source: gh-pages branch, / (root).
set -euo pipefail
shopt -s nullglob

MONITOR_DIR="$HOME/Projects/sitemap-updata-crawl"
PAGES_DIR="$MONITOR_DIR/.gh-pages"
PAGES_BRANCH="gh-pages"
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
        if git push "$PUSH_URL" "$PAGES_BRANCH"; then
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

# Ensure the gh-pages worktree exists and is up to date with the remote.
git fetch origin "$PAGES_BRANCH"
if [ ! -d "$PAGES_DIR" ]; then
    git worktree add "$PAGES_DIR" "$PAGES_BRANCH"
fi
git -C "$PAGES_DIR" reset --hard "origin/$PAGES_BRANCH"

# Run the monitor. HTML is written into the gh-pages worktree
# (config.yaml html_report.output_dir = ./.gh-pages); JSON state stays local.
source .venv/bin/activate
if python -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports; then
    EXIT_CODE=0
else
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [error] monitor failed with exit code ${EXIT_CODE}"
    exit "$EXIT_CODE"
fi

# Rebuild the index so it reflects whatever daily pages are present.
python -c "
from monitor.local_store import _render_html_index, _write_text
from pathlib import Path
output_root = Path('.gh-pages')
_write_text(output_root / 'index.html', _render_html_index(output_root))
"

# Commit and push the gh-pages worktree only (embed token in URL for headless cron).
GH_TOKEN=$(GH_CONFIG_DIR=~/.config/gh-file /Users/liike/.local/bin/gh auth token 2>/dev/null)
if [ -z "$GH_TOKEN" ]; then
    echo "[error] Failed to get GitHub token"
    exit 1
fi
PUSH_URL="https://Dear-linko:${GH_TOKEN}@github.com/Dear-linko/sitemap-updata-crawl.git"

cd "$PAGES_DIR"
git add daily/ index.html .nojekyll
if ! git diff --cached --quiet; then
    git commit -m "Auto-update: $(date +%Y-%m-%d)"
    push_with_retry
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] no report changes to commit"
fi

exit $EXIT_CODE
