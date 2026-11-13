"""Standardized computer-use actions. The LLM (if used) outputs these; PyAutoGUI does not."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional


ACTIONS = (
    "OPEN_APP",
    "CLOSE_APP",
    "OPEN_URL",
    "CLICK",
    "DOUBLE_CLICK",
    "TYPE",
    "PRESS_KEY",
    "SCROLL",
    "SELECT",
    "HOVER",
    "BACK",
    "FORWARD",
    "REFRESH",
    "NEW_TAB",
    "CLOSE_TAB",
    "SWITCH_TAB",
    "MINIMIZE_WINDOW",
    "RESTORE_WINDOW",
    "WAIT",
    "ASK_USER",
    "CONFIRM",
    "START_TASK",
    "END_TASK",
    "STOP",
)


@dataclass
class ComputerAction:
    type: str
    target: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    timeout: float = 8.0
    verify: str = "screen_changed"
    spoken: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def intent_to_action(intent: str, entities: Dict[str, Any], *, confidence: float = 0.0, spoken: str = "") -> Optional[ComputerAction]:
    mapping = {
        "open_app": "OPEN_APP",
        "close_app": "CLOSE_APP",
        "open_url": "OPEN_URL",
        "click_text": "CLICK",
        "click_button": "CLICK",
        "type_text": "TYPE",
        "fill_form": "TYPE",
        "press_key": "PRESS_KEY",
        "scroll": "SCROLL",
        "select_option": "SELECT",
        "browser_back": "BACK",
        "browser_forward": "FORWARD",
        "browser_refresh": "REFRESH",
        "new_tab": "NEW_TAB",
        "close_tab": "CLOSE_TAB",
        "switch_tab": "SWITCH_TAB",
        "minimize_window": "MINIMIZE_WINDOW",
        "restore_window": "RESTORE_WINDOW",
        "wait": "WAIT",
        "search_web": "OPEN_URL",
        "start_task": "START_TASK",
        "end_task": "END_TASK",
        "emergency_stop": "STOP",
    }
    kind = mapping.get(intent)
    if not kind:
        return None
    params = dict(entities or {})
    if kind == "OPEN_URL" and intent == "search_web" and params.get("query") and not params.get("url"):
        q = str(params.get("query") or "")
        if "." in q and " " not in q.strip():
            params["url"] = q.strip()
        else:
            from urllib.parse import quote_plus

            params["url"] = f"https://www.google.com/search?q={quote_plus(q)}"
    return ComputerAction(type=kind, target=params, parameters=params, confidence=confidence, spoken=spoken)
