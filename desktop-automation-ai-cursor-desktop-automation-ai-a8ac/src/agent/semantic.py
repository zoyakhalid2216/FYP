"""Spoken click phrases → canonical UI targets (case/synonym, not exact text)."""

from __future__ import annotations

import re

from src.vision.ocr_text import normalize_ocr_query

_LOGIN_WORDS = frozenset({"login", "log", "sign", "signin", "logon", "sso", "auth", "account"})
_MICROSOFT = frozenset({"microsoft", "ms", "msft", "azure"})
_ODOO = frozenset({"odoo"})
_FILLER = frozenset({"in", "with"})


def expand_click_query(raw: str) -> str:
    """Map 'click Microsoft' / 'SIGN IN WITH MICROSOFT' onto the same target string."""
    t = normalize_ocr_query(raw)
    if not t:
        return t
    toks = set(re.findall(r"[a-z0-9]+", t))
    if toks & _MICROSOFT and not (toks & _ODOO):
        t = re.sub(r"\b(msft|ms)\b", "microsoft", t)
        t = " ".join(t.split())
        toks = set(re.findall(r"[a-z0-9]+", t))
        if toks <= (_MICROSOFT | _LOGIN_WORDS | _FILLER):
            return "login with microsoft"
        return t
    if toks & _ODOO and not (toks & _MICROSOFT):
        if toks <= (_ODOO | _LOGIN_WORDS | _FILLER):
            return "login with odoo"
        return t
    return t
