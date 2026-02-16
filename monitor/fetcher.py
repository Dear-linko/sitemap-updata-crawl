from __future__ import annotations

import hashlib
from typing import Optional

import httpx

from monitor.types import FetchResult


class SitemapFetcher:
    def __init__(self, timeout_sec: int, user_agent: str, client: Optional[httpx.Client] = None):
        self._owns_client = client is None
        self.client = client or httpx.Client(
            timeout=timeout_sec,
            headers={"User-Agent": user_agent},
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def fetch_head(self, url: str) -> FetchResult:
        try:
            response = self.client.head(url)
            return FetchResult(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                http_status=response.status_code,
                error=None if response.status_code < 500 else f"HEAD failed: {response.status_code}",
            )
        except httpx.HTTPError as exc:
            return FetchResult(error=f"HEAD request error: {exc}")

    def fetch_content_hash(self, url: str) -> FetchResult:
        response = self._fetch_get(url)
        if response.error or response.content_bytes is None:
            return response

        content_hash = hashlib.sha256(response.content_bytes).hexdigest()
        response.content_hash = content_hash
        return response

    def fetch_page(self, url: str) -> FetchResult:
        return self._fetch_get(url)

    def _fetch_get(self, url: str) -> FetchResult:
        try:
            response = self.client.get(url)
            if response.status_code >= 500:
                return FetchResult(
                    http_status=response.status_code,
                    error=f"GET failed: {response.status_code}",
                )
            return FetchResult(
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                http_status=response.status_code,
                content_bytes=response.content,
            )
        except httpx.HTTPError as exc:
            return FetchResult(error=f"GET request error: {exc}")
