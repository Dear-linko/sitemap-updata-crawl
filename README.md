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

## 数据文件

- baseline：`./data/baseline.json`
- 日报目录：`./data/reports/`
- 日报文件：`YYYY-MM-DD.json`（仅当天有新增时生成/追加）

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
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
- `targets[].name`：目标名（必须唯一）
- `targets[].url`：sitemap 地址
- `targets[].enabled`：是否启用
- `targets[].webhook_url`：可选

## 使用

1. 初始化（只需一次）：

```bash
python -m monitor init-state --baseline ./data/baseline.json --reports-dir ./data/reports
```

2. 日常运行（主命令）：

```bash
python -m monitor run-once --config ./config.yaml --baseline ./data/baseline.json --reports-dir ./data/reports
```

3. 查看帮助：

```bash
python -m monitor --help
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
