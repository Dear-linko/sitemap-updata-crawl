from __future__ import annotations

import gzip
import re
import xml.etree.ElementTree as ET
from typing import List, Set

_URL_RE = re.compile(r"https?://[^\s<\"]+")


def extract_sitemap_urls(content: bytes, source_url: str) -> List[str]:
    payload = _maybe_gunzip(content, source_url)

    urls = _extract_from_xml(payload)
    if urls:
        return sorted(urls)

    text = payload.decode("utf-8", errors="replace")
    line_urls = {
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith(("http://", "https://"))
    }
    if line_urls:
        return sorted(line_urls)

    return sorted(set(_URL_RE.findall(text)))


def _maybe_gunzip(content: bytes, source_url: str) -> bytes:
    if source_url.lower().endswith(".gz") or content.startswith(b"\x1f\x8b"):
        try:
            return gzip.decompress(content)
        except OSError:
            return content
    return content


def _extract_from_xml(content: bytes) -> Set[str]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return set()

    urls: Set[str] = set()
    for loc in root.findall(".//{*}loc"):
        if loc.text:
            value = loc.text.strip()
            if value.startswith(("http://", "https://")):
                urls.add(value)
    return urls
