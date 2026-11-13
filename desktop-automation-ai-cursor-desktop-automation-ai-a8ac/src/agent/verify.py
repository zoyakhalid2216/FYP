"""Verify that a click actually changed the page (URL / title / pixels)."""

from __future__ import annotations

from typing import Any, Dict

from src.agent.a11y import page_signature
from src.agent.chrome_debug import page_identity

_AUTH_HINTS = (
    "login.microsoftonline.com",
    "microsoftonline.com",
    "login.live.com",
    "login.microsoft.com",
    "accounts.google.com",
    "appleid.apple.com",
    "facebook.com/login",
    "oauth",
)


def page_snapshot() -> Dict[str, Any]:
    """Merge UIA window identity with optional Chrome DevTools tab list."""
    a11y = page_signature()
    chrome = page_identity()
    url = str(a11y.get("url") or chrome.get("url") or "")
    title = str(a11y.get("title") or chrome.get("title") or "")
    urls = list(chrome.get("urls") or [])
    if url and url not in urls:
        urls.insert(0, url)
    titles = list(chrome.get("titles") or [])
    if title and title not in titles:
        titles.insert(0, title)
    return {
        "title": title,
        "url": url,
        "urls": urls,
        "titles": titles,
        "devtools": bool(chrome.get("available")),
    }


def page_changed(before: Dict[str, Any] | None, after: Dict[str, Any] | None) -> bool:
    """True when the browser navigated or a Microsoft/Google auth page appeared."""
    before = before or {}
    after = after or {}
    before_url = str(before.get("url") or "")
    after_url = str(after.get("url") or "")
    if before_url and after_url and before_url != after_url:
        return True
    before_title = str(before.get("title") or "")
    after_title = str(after.get("title") or "")
    if before_title and after_title and before_title != after_title:
        return True
    after_blob = " ".join(after.get("urls") or [after_url]).lower()
    before_blob = " ".join(before.get("urls") or [before_url]).lower()
    for hint in _AUTH_HINTS:
        if hint in after_blob and hint not in before_blob:
            return True
    after_titles = " ".join(after.get("titles") or [after_title]).lower()
    before_titles = " ".join(before.get("titles") or [before_title]).lower()
    if after_titles and before_titles and after_titles != before_titles:
        return True
    return False


def click_succeeded(
    before: Dict[str, Any] | None,
    after: Dict[str, Any] | None,
    frame_changed: bool,
) -> bool:
    if frame_changed:
        return True
    return page_changed(before, after)
