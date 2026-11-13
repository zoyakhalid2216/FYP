"""Correct common STT mistakes without inventing a different command."""

from __future__ import annotations

import re

_REPLACEMENTS = (
    (r"\bcrohm\b", "chrome"),
    (r"\bchrom\b", "chrome"),
    (r"\bchorme\b", "chrome"),
    (r"\bgoogle chrome\b", "chrome"),
    (r"\bmicro\s*soft\b", "microsoft"),
    (r"\bmicrosoft\b", "microsoft"),
    (r"\blog\s+in\b", "login"),
    (r"\bsign\s+in\b", "sign in"),
    (r"\be[\s-]?mail\b", "email"),
    (r"\bhorizon\s+ucp\b", "horizon.ucp.edu.pk"),
    (r"\bhorizon\s+up\s+edu\b", "horizon.ucp.edu.pk"),
    (r"\bnote\s*pad\b", "notepad"),
    (r"\byou\s*tube\b", "youtube"),
    (r"\bgo to sleep\b", "dai sleep"),
    (r"\bfisrt\b", "first"),
    (r"\bfist\s+result\b", "first result"),
    (r"\bfist\s+link\b", "first link"),
    (r"\bfrist\b", "first"),
    (r"\bsecand\b", "second"),
    (r"\bsecon\s+d\b", "second"),
    (r"\bthrid\b", "third"),
    (r"\blinks\b", "link"),
)


def normalize_command(text: str) -> str:
    t = " ".join((text or "").split())
    if not t:
        return ""
    out = t
    for pattern, repl in _REPLACEMENTS:
        out = re.sub(pattern, repl, out, flags=re.I)
    return " ".join(out.split()).strip(" .,!?")


def is_final_transcript(*, is_final: bool) -> bool:
    """Partial/interim speech must never enter execution."""
    return bool(is_final)
