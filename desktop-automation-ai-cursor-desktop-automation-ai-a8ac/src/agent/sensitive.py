"""Detect and redact sensitive values. Never persist passwords/OTPs."""

from __future__ import annotations

import re
from typing import Tuple

_SENSITIVE_HINT = re.compile(
    r"\b(password|passcode|pin|otp|one[\s-]?time|security code|cvv|"
    r"card number|account number|iban|routing)\b",
    re.I,
)
_SECRET_VALUE = re.compile(
    r"(password|otp|pin|passcode|token|secret|cvv)\s*[:=]\s*\S+",
    re.I,
)


def is_sensitive_request(text: str) -> bool:
    return bool(_SENSITIVE_HINT.search(text or ""))


def redact(text: str) -> str:
    t = text or ""
    t = _SECRET_VALUE.sub(r"\1: [redacted]", t)
    if is_sensitive_request(t) and re.search(r"\b(type|enter|write)\b", t, re.I):
        return "Entered secret into a secure field."
    return t


def classify_type_request(text: str) -> Tuple[bool, str]:
    """Return (is_sensitive, safe_label)."""
    if is_sensitive_request(text):
        return True, "password"
    return False, "text"


def history_line_for_type(*, sensitive: bool, field: str = "") -> str:
    if sensitive:
        return "Entered password into password field." if "pass" in (field or "password").lower() else "Entered a secret value."
    if field:
        return f"Typed into {field}."
    return "Typed text."
