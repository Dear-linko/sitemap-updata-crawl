from pathlib import Path

from monitor.config import load_config


def test_load_config_parses_html_and_telegram_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval_minutes: 5
request_timeout_sec: 20
user_agent: "ua"
targets:
  - name: "main"
    url: "https://example.com/sitemap.xml"
    enabled: true
html_report:
  enabled: true
  output_dir: "./data/reports_html"
telegram:
  enabled: true
  bot_token: "yaml-token"
  chat_id: "yaml-chat"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(str(config_path))
    assert config.html_report.enabled is True
    assert config.html_report.output_dir == "./data/reports_html"
    assert config.telegram.enabled is True
    assert config.telegram.bot_token == "yaml-token"
    assert config.telegram.chat_id == "yaml-chat"


def test_load_config_telegram_env_overrides_yaml(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
interval_minutes: 5
request_timeout_sec: 20
user_agent: "ua"
targets:
  - name: "main"
    url: "https://example.com/sitemap.xml"
    enabled: true
telegram:
  enabled: true
  bot_token: "yaml-token"
  chat_id: "yaml-chat"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "env-chat")

    config = load_config(str(config_path))
    assert config.telegram.bot_token == "env-token"
    assert config.telegram.chat_id == "env-chat"
