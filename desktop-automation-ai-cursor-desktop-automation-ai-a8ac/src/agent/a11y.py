"""Windows UI Automation scan. Soft-fails when pywinauto is missing (Linux tests)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.elements import ScreenElement

_WINDOW_HINTS = (
    "chrome",
    "edge",
    "msedge",
    "firefox",
    "brave",
    "opera",
    "horizon",
    "ucp",
    "login",
    "microsoft",
    "odoo",
    "sign in",
)
_SKIP_NAME = re.compile(
    r"^(chrome legacy window|google chrome|microsoft edge|maximize|minimize|"
    r"close|restore|restore pane|system)$",
    re.I,
)
_MAX_DESCENDANTS = 400
_MAX_ELEMENTS = 80


def collect_elements(region: Optional[Dict[str, Any]] = None) -> List[ScreenElement]:
    """Best-effort UIA tree. Returns [] if pywinauto is not installed or the scan fails."""
    try:
        from pywinauto import Desktop  # type: ignore
    except Exception:
        return []
    found: List[ScreenElement] = []
    left = int((region or {}).get("left") or 0)
    top = int((region or {}).get("top") or 0)
    try:
        desk = Desktop(backend="uia")
        windows = _candidate_windows(desk)
        idx = 0
        for win in windows[:6]:
            try:
                ctrls = win.descendants()[:_MAX_DESCENDANTS]
            except Exception:
                continue
            for ctrl in ctrls:
                if idx >= _MAX_ELEMENTS:
                    return found
                try:
                    text = _ctrl_name(ctrl)
                    if not text or len(text) > 80 or _SKIP_NAME.match(text):
                        continue
                    rec = ctrl.rectangle()
                    width = int(rec.width())
                    height = int(rec.height())
                    if width < 6 or height < 6:
                        continue
                    kind = _ctrl_kind(ctrl)
                    found.append(
                        ScreenElement(
                            id=f"a11y-{idx}",
                            type=kind,
                            text=text,
                            role=str(getattr(getattr(ctrl, "element_info", None), "control_type", "") or ""),
                            x=max(0, int(rec.left) - left),
                            y=max(0, int(rec.top) - top),
                            width=max(8, width),
                            height=max(8, height),
                            confidence=0.94,
                            source="ACCESSIBILITY",
                        )
                    )
                    idx += 1
                except Exception:
                    continue
    except Exception:
        return []
    return found


def page_signature() -> Dict[str, Any]:
    """Foreground window title plus address-bar URL when UIA exposes it."""
    title = ""
    url = ""
    try:
        from pywinauto import Desktop  # type: ignore

        desk = Desktop(backend="uia")
        win = desk.get_active()
        if win is None:
            return {"title": "", "url": ""}
        title = str(win.window_text() or "")
        try:
            ctrls = win.descendants()[:80]
        except Exception:
            ctrls = []
        for ctrl in ctrls:
            val = _ctrl_value(ctrl)
            if val.startswith("http://") or val.startswith("https://"):
                url = val
                break
            name = _ctrl_name(ctrl).lower()
            if "address" in name and val:
                url = val
                break
    except Exception:
        return {"title": title, "url": url}
    return {"title": title, "url": url}


def _candidate_windows(desk) -> list:
    windows = []
    try:
        for win in desk.windows():
            title = (win.window_text() or "").lower()
            if any(k in title for k in _WINDOW_HINTS):
                windows.append(win)
    except Exception:
        windows = []
    try:
        active = desk.get_active()
        if active is not None and active not in windows:
            windows.insert(0, active)
    except Exception:
        pass
    return windows


def _ctrl_name(ctrl) -> str:
    try:
        info = ctrl.element_info
        name = str(getattr(info, "name", None) or "").strip()
        if name:
            return name
    except Exception:
        pass
    try:
        return str(ctrl.window_text() or "").strip()
    except Exception:
        return ""


def _ctrl_value(ctrl) -> str:
    try:
        if hasattr(ctrl, "get_value"):
            return str(ctrl.get_value() or "").strip()
    except Exception:
        pass
    try:
        props = ctrl.legacy_properties()
        return str((props or {}).get("Value") or "").strip()
    except Exception:
        return ""


def _ctrl_kind(ctrl) -> str:
    try:
        ctype = str(ctrl.element_info.control_type)
    except Exception:
        return "text"
    if "Edit" in ctype:
        return "input"
    if "Hyperlink" in ctype:
        return "link"
    if "Button" in ctype or "TabItem" in ctype or "ListItem" in ctype:
        return "button"
    return "text"
