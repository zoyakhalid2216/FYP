"""Optional Chrome DevTools HTTP (/json) — page URL/title without a WebSocket DOM stack."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List

DEFAULT_PORT = 9222


def list_pages(port: int = DEFAULT_PORT, timeout: float = 0.4) -> List[Dict[str, Any]]:
    """Return Chrome/Edge page targets, or [] if debugging is off / port closed."""
    url = f"http://127.0.0.1:{int(port)}/json"
    try:
        req = urllib.request.Request(url, headers={"Host": "127.0.0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    pages = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if str(item.get("type") or "page") != "page":
            continue
        pages.append(
            {
                "url": str(item.get("url") or ""),
                "title": str(item.get("title") or ""),
                "id": str(item.get("id") or ""),
            }
        )
    return pages


def page_identity(port: int = DEFAULT_PORT) -> Dict[str, Any]:
    pages = list_pages(port=port)
    urls = [p["url"] for p in pages if p.get("url")]
    titles = [p["title"] for p in pages if p.get("title")]
    first = pages[0] if pages else {}
    return {
        "url": str(first.get("url") or ""),
        "title": str(first.get("title") or ""),
        "urls": urls,
        "titles": titles,
        "available": bool(pages),
    }
