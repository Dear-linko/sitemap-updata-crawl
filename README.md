# sitemap-monitor

`sitemap-monitor` 用于监控多个 sitemap（`xml` / `xml.gz` / `txt`）中的 URL 新增，提取新增页面标题（`h1` 优先，缺失降级 `h2`），并自动生成可直接打开的 Google Trends 查询链接。

## 核心功能

- 多站点 sitemap 监控。
- 首次运行建立 baseline，不计为新增。
- 后续只比较“当前 URL 集合 - baseline URL 集合”。
- 仅当有新增时写入日报（无新增时 `report skipped`）。
- 标题提取规则：`h1 -> h2 -> 无结果`。
- 关键词输出：
  - 目标级：`targets[].keywords`
  - 运行级：`keywords`
- 自动生成 Google Trends 链接：
  - 字段名：`google-trends`
  - 值：链接数组（每 5 个关键词一条链接，最近30天、全球）
- 可选 HTML 日汇总：当天有新增时更新 `.gh-pages/daily/YYYY-MM-DD.html`，并刷新 `.gh-pages/index.html`（`.gh-pages` 是 `gh-pages` 分支的 git worktree，由 `sync-reports.sh` 提交并推送，GitHub Pages 从 `gh-pages` 分支发布）
- 可选 Telegram 汇总提醒：每次运行有新增时发 1 条摘要消息

## 数据文件

- baseline：`./data/baseline.json`
- 日报目录：`./data/reports/`
- 日报文件：`YYYY-MM-DD.json`（仅当天有新增时生成/追加）
- HTML 日报目录（可选）：`./.gh-pages/`（`gh-pages` 分支的 worktree；GitHub Pages 设置选 `gh-pages` 分支 `/(root)`。该目录已被 `.gitignore`，不会污染 `main`）

## 环境要求

- Python `3.11`（已在本项目验证）

先检查版本：

```bash
python3.11 -V
```

## 快速开始（推荐）

1. 创建并进入虚拟环境：

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

2. 安装依赖（注意 `'.[dev]'` 必须加引号，避免 zsh 通配）：

```bash
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

3. 检查依赖是否齐全：

```bash
python -c "import yaml, pydantic, httpx; print('deps ok')"
```

4. 初始化状态（只需一次）：

```bash
python -m monitor init-state --baseline ./data/baseline.json --reports-dir ./data/reports
```

5. 运行一次检测：

```bash
python -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports
```

## 使用 Makefile（新手友好）

本项目提供了 `Makefile`，可直接用：

```bash
make install
make doctor
make init-state
make run-once
make html-rebuild
make test
```

各命令作用：

- `make install`：创建 `.venv` 并安装项目依赖（含 dev 依赖）
- `make doctor`：检查当前解释器和依赖是否正确
- `make init-state`：初始化 `baseline.json` 与 `reports` 目录（首次一次）
- `make run-once`：执行一次 sitemap 监控主流程
- `make html-rebuild`：从 `reports/*.json` 全量重建 HTML（不依赖“本次有新增”）
- `make test`：运行测试用例

推荐顺序：

- 首次：`make install` -> `make doctor` -> `make init-state` -> `make run-once`
- 日常：`make run-once`
- 需要强制刷新 HTML：`make html-rebuild`
- 改代码后回归：`make test`

如需自定义配置文件，可覆盖变量：

```bash
make run-once CONFIG=./config.yaml BASELINE=./data/baseline.json REPORTS_DIR=./data/reports
make html-rebuild REPORTS_DIR=./data/reports HTML_DIR=./.gh-pages
```

## 配置

复制示例：

```bash
cp config.example.yaml config.yaml
```

示例：

```yaml
interval_minutes: 5
request_timeout_sec: 20
user_agent: "sitemap-monitor/1.0"
html_report:
  enabled: true
  output_dir: "./.gh-pages"
telegram:
  enabled: false
  bot_token: null
  chat_id: null
targets:
  - name: "gamemonetize"
    url: "https://gamemonetize.com/sitemap.xml"
    enabled: true
  - name: "poki-games"
    url: "https://poki.com/en/sitemaps/games.xml"
    enabled: true
```

字段说明：

- `interval_minutes`：轮询间隔（给 cron 参考，程序本身单次运行）
- `request_timeout_sec`：请求超时（秒）
- `user_agent`：请求头 UA
- `html_report.enabled`：是否生成 HTML 日汇总
- `html_report.output_dir`：HTML 输出目录
- `telegram.enabled`：是否启用 Telegram 通知
- `telegram.bot_token`：Telegram Bot Token（可被环境变量覆盖）
- `telegram.chat_id`：Telegram Chat ID（可被环境变量覆盖）
- `targets[].name`：目标名（必须唯一）
- `targets[].url`：sitemap 地址
- `targets[].enabled`：是否启用
- `targets[].webhook_url`：可选

Telegram 环境变量优先级：

- `TELEGRAM_BOT_TOKEN` > `telegram.bot_token`
- `TELEGRAM_CHAT_ID` > `telegram.chat_id`

## 使用（命令行）

- 初始化（只需一次）：

```bash
python -m monitor init-state --baseline ./data/baseline.json --reports-dir ./data/reports
```

- 日常运行（主命令）：

```bash
python -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports
```

- 强制重建 HTML（不依赖“本次有新增”）：

```bash
python -m monitor html-rebuild --reports-dir ./data/reports --output-dir ./.gh-pages
```

- 查看帮助：

```bash
python -m monitor --help
```

## 常见问题

- `zsh: no matches found: .[dev]`
  - 原因：zsh 把 `.[dev]` 当通配符。
  - 修复：使用 `python -m pip install -e '.[dev]'`（带引号）。

- `ModuleNotFoundError: No module named 'yaml'`
  - 原因：当前解释器没有安装项目依赖，或没在 `.venv` 中执行。
  - 修复：

```bash
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -c "import yaml; print('ok')"
```

## 日报结构（关键字段）

每条运行记录（`reports/YYYY-MM-DD.json` 的数组元素）包含：

- `checked_at`
- `summary`
  - `processed`
  - `updated_targets`
  - `added_urls_total`
  - `errors`
  - `heading_ok_total`
  - `heading_failed_total`
- `keywords`
  - `keywords`: 运行级关键词数组（去重）
- `google-trends`
  - Google Trends 查询链接数组（每 5 个关键词一条）
- `targets[]`（仅本次有新增的目标）
  - `added_urls`
  - `heading_results[]`
    - `url`
    - `http_status`
    - `heading`
    - `heading_tag`（`h1` / `h2` / `null`）
    - `ok`
    - `reason`（`ok_h1` / `ok_h2` / `fetch_failed` / `heading_not_found` / `html_parse_error`）
  - `keywords`
    - `keywords`: 目标级关键词数组（去重）

HTML 日汇总：

- 索引页：`.gh-pages/index.html`
- 每日报告：`.gh-pages/daily/YYYY-MM-DD.html`
- 索引页每行展示：日期、last checked、`runs` / `added` / `targets` 关键数量
- 详情页包含：
  - `Heading Collection`（支持一键复制所有 heading，逗号分隔）
  - `Trends Link Collection`（样式化链接列表）
  - `Heading Results`（表格）

## 常用查询命令

```bash
# baseline 目标数量
jq '.targets | length' ./data/baseline.json

# 某目标 baseline URL 数量
jq '.targets["gamemonetize"].url_count' ./data/baseline.json

# 今天最近 3 条“有新增”的记录
jq '.[-3:]' ./data/reports/$(date +%F).json

# 新增 URL 明细
jq '[.[] | .targets[] | {name, checked_at, added_count, added_urls}]' ./data/reports/$(date +%F).json

# 标题提取失败项
jq '[.[] | .targets[] | .heading_results[] | select(.ok == false)]' ./data/reports/$(date +%F).json

# 运行级关键词
jq '[.[] | {checked_at, keywords: .keywords.keywords}]' ./data/reports/$(date +%F).json

# Google Trends 链接
jq '[.[] | {checked_at, google_trends: ."google-trends"}]' ./data/reports/$(date +%F).json
```

## cron 示例

```cron
*/5 * * * * cd /path/to/sitemap-updata-crawl && /usr/bin/python3 -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports >> ./logs/monitor.log 2>&1
```
