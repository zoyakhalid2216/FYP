"""Browser actions via keyboard — works for Chrome/Edge without a hard-coded site."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import quote_plus


def ensure_url(raw: str) -> str:
    t = (raw or "").strip()
    if not t:
        return ""
    if t.startswith(("http://", "https://")):
        return t
    if " " not in t and "." in t:
        return "https://" + t.lstrip("/")
    return f"https://www.google.com/search?q={quote_plus(t)}"


def apply_browser(automation, action_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    kind = (action_type or "").upper()
    if kind == "OPEN_URL":
        url = ensure_url(str(params.get("url") or params.get("query") or params.get("host") or ""))
        if not url:
            raise RuntimeError("No URL to open.")
        return automation.open_url(url)
    if kind == "BACK":
        return automation.press("alt+left")
    if kind == "FORWARD":
        return automation.press("alt+right")
    if kind == "REFRESH":
        return automation.press("f5")
    if kind == "NEW_TAB":
        return automation.press("ctrl+t")
    if kind == "CLOSE_TAB":
        return automation.press("ctrl+w")
    if kind == "SWITCH_TAB":
        which = str(params.get("which") or params.get("direction") or "next").lower()
        if "prev" in which or "previous" in which or which == "left":
            return automation.press("ctrl+shift+tab")
        return automation.press("ctrl+tab")
    if kind == "CLOSE_APP":
        return automation.press("alt+f4")
    raise RuntimeError(f"Unsupported browser action: {action_type}")
