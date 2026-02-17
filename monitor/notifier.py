from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from monitor.types import NotifyPayload

LOGGER = logging.getLogger(__name__)


class WebhookNotifier:
    def __init__(self, timeout_sec: int, client: Optional[httpx.Client] = None):
        self._owns_client = client is None
        self.client = client or httpx.Client(timeout=timeout_sec)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def send(self, webhook_url: str, payload: NotifyPayload) -> bool:
        data = payload.to_feishu() if "feishu" in webhook_url else payload.to_wecom()

        for attempt in range(1, 4):
            try:
                response = self.client.post(webhook_url, json=data)
                if 200 <= response.status_code < 300:
                    return True

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_s = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt - 1)
                    LOGGER.warning("Webhook rate limited for %s, retry in %ss", _mask_url(webhook_url), sleep_s)
                    time.sleep(sleep_s)
                    continue

                if response.status_code >= 500:
                    sleep_s = 2 ** (attempt - 1)
                    LOGGER.warning("Webhook 5xx for %s, retry in %ss", _mask_url(webhook_url), sleep_s)
                    time.sleep(sleep_s)
                    continue

                LOGGER.error("Webhook rejected by remote for %s: status=%s", _mask_url(webhook_url), response.status_code)
                return False
            except httpx.HTTPError as exc:
                sleep_s = 2 ** (attempt - 1)
                LOGGER.warning("Webhook HTTP error for %s: %s; retry in %ss", _mask_url(webhook_url), exc, sleep_s)
                time.sleep(sleep_s)

        return False

    def send_telegram(self, bot_token: str, chat_id: str, text: str) -> bool:
        token = bot_token.strip()
        target_chat = chat_id.strip()
        if not token or not target_chat:
            LOGGER.error("Telegram token/chat_id is empty")
            return False

        telegram_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "disable_web_page_preview": True,
        }

        for attempt in range(1, 4):
            try:
                response = self.client.post(telegram_url, json=payload)
                if 200 <= response.status_code < 300:
                    return True

                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_s = int(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt - 1)
                    LOGGER.warning("Telegram rate limited, retry in %ss", sleep_s)
                    time.sleep(sleep_s)
                    continue

                if response.status_code >= 500:
                    sleep_s = 2 ** (attempt - 1)
                    LOGGER.warning("Telegram 5xx, retry in %ss", sleep_s)
                    time.sleep(sleep_s)
                    continue

                LOGGER.error("Telegram rejected request: status=%s", response.status_code)
                return False
            except httpx.HTTPError as exc:
                sleep_s = 2 ** (attempt - 1)
                LOGGER.warning("Telegram HTTP error: %s; retry in %ss", exc, sleep_s)
                time.sleep(sleep_s)

        return False


def _mask_url(url: str) -> str:
    if len(url) <= 10:
        return "***"
    return f"{url[:8]}***{url[-4:]}"
