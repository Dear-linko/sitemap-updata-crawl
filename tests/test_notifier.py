import httpx

from monitor.notifier import WebhookNotifier


def test_send_telegram_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "api.telegram.org"
        return httpx.Response(200, json={"ok": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = WebhookNotifier(timeout_sec=2, client=client)
    ok = notifier.send_telegram(bot_token="token", chat_id="123", text="hello")
    assert ok is True
    notifier.close()


def test_send_telegram_retries_on_429(monkeypatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("monitor.notifier.time.sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = WebhookNotifier(timeout_sec=2, client=client)
    ok = notifier.send_telegram(bot_token="token", chat_id="123", text="hello")
    assert ok is True
    assert calls["n"] == 3
    notifier.close()


def test_send_telegram_returns_false_after_5xx_retries(monkeypatch) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(502, text="bad gateway")

    monkeypatch.setattr("monitor.notifier.time.sleep", lambda _: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    notifier = WebhookNotifier(timeout_sec=2, client=client)
    ok = notifier.send_telegram(bot_token="token", chat_id="123", text="hello")
    assert ok is False
    assert calls["n"] == 3
    notifier.close()
