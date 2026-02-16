from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional, Tuple

_WS_RE = re.compile(r"\s+")


class _HeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._active_tag: Optional[str] = None
        self._active_chunks: list[str] = []
        self._h1_values: list[str] = []
        self._h2_values: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        lower = tag.lower()
        if lower in {"h1", "h2"}:
            self._active_tag = lower
            self._active_chunks = []

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        lower = tag.lower()
        if self._active_tag == lower:
            value = _normalize(" ".join(self._active_chunks))
            if value:
                if lower == "h1":
                    self._h1_values.append(value)
                else:
                    self._h2_values.append(value)
            self._active_tag = None
            self._active_chunks = []

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._active_tag in {"h1", "h2"}:
            self._active_chunks.append(data)

    def first_non_empty_h1(self) -> Optional[str]:
        return self._h1_values[0] if self._h1_values else None

    def first_non_empty_h2(self) -> Optional[str]:
        return self._h2_values[0] if self._h2_values else None


def _normalize(value: str) -> Optional[str]:
    clean = _WS_RE.sub(" ", value).strip()
    return clean or None


def extract_heading(html_bytes: bytes) -> Tuple[Optional[str], Optional[str], str]:
    try:
        text = html_bytes.decode("utf-8", errors="replace")
        parser = _HeadingParser()
        parser.feed(text)
        parser.close()
    except Exception:
        return None, None, "html_parse_error"

    h1 = parser.first_non_empty_h1()
    if h1:
        return h1, "h1", "ok_h1"

    h2 = parser.first_non_empty_h2()
    if h2:
        return h2, "h2", "ok_h2"

    return None, None, "heading_not_found"
