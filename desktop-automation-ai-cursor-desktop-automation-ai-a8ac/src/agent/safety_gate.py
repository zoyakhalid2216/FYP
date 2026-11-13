"""Block destructive / financial actions until the user confirms."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_DESTRUCTIVE = re.compile(
    r"\b(delete|remove|uninstall|format|wipe|drop|erase)\b",
    re.I,
)
_SUBMIT = re.compile(
    r"\b(submit|send (email|message|mail)|post (this|it|publicly)|publish)\b",
    re.I,
)
_PAYMENT = re.compile(
    r"\b(pay|purchase|buy now|checkout|transfer money|send money|"
    r"confirm payment|place order|rs\.?\s*\d|pkr|usd|\$\d)\b",
    re.I,
)


def risk_for(text: str, *, target: str = "") -> Optional[str]:
    blob = f"{text or ''} {target or ''}"
    if _PAYMENT.search(blob):
        return "payment"
    if _DESTRUCTIVE.search(blob):
        return "destructive"
    if _SUBMIT.search(blob):
        return "submit"
    return None


def confirmation_prompt(risk: str, *, target: str = "") -> str:
    shown = (target or "this action").strip() or "this action"
    if risk == "payment":
        return f"I found a payment action ({shown}). Do you want me to proceed?"
    if risk == "destructive":
        return f"This looks destructive ({shown}). Do you want me to continue?"
    return f"The form is ready to submit ({shown}). Do you want me to click it?"


def must_confirm(text: str, *, target: str = "") -> Tuple[bool, str]:
    risk = risk_for(text, target=target)
    if not risk:
        return False, ""
    return True, confirmation_prompt(risk, target=target)
