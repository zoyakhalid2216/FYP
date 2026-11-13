"""Rank on-screen elements against a spoken target. Never pick randomly among logins."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import List, Sequence

from src.agent.elements import ScreenElement
from src.agent.semantic import expand_click_query
from src.vision.ocr_text import brand_tokens, normalize_ocr_query

HIGH = 0.90
MEDIUM = 0.65

_SYNONYMS = {
    "login": ("login", "log in", "sign in", "signin", "logon", "sso"),
    "microsoft": ("microsoft", "micro soft", "ms", "msft", "office 365", "azure"),
    "odoo": ("odoo",),
    "email": ("email", "e-mail", "mail", "username", "user name", "account"),
    "password": ("password", "passcode", "passwd"),
    "next": ("next", "continue", "proceed"),
    "submit": ("submit", "send", "confirm"),
    "search": ("search", "google", "find"),
}


@dataclass
class RankedMatch:
    element: ScreenElement
    score: float
    reason: str = ""


@dataclass
class MatchResult:
    query: str
    matches: List[RankedMatch] = field(default_factory=list)
    ambiguous: bool = False
    message: str = ""

    @property
    def best(self) -> RankedMatch | None:
        return self.matches[0] if self.matches else None

    @property
    def confidence(self) -> float:
        return self.best.score if self.best else 0.0

    @property
    def band(self) -> str:
        c = self.confidence
        if c >= HIGH:
            return "high"
        if c >= MEDIUM:
            return "medium"
        return "low"


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _expand(token: str) -> set:
    out = {token}
    for _key, vals in _SYNONYMS.items():
        if token in vals or token == _key:
            out.update(vals)
            out.add(_key)
    return out


def score_element(query: str, element: ScreenElement) -> float:
    q = expand_click_query(query) or normalize_ocr_query(query)
    text = normalize_ocr_query(element.text or "")
    if not q or not text:
        return 0.0
    if q == text:
        score = 0.99
    elif q in text:
        score = 0.96 if len(q) >= 4 else 0.82
    else:
        q_brands = brand_tokens(q)
        text_toks = set(_tokens(text))
        if q_brands and q_brands <= text_toks:
            score = 0.96
        elif text in q and len(text) >= 4:
            score = round(0.70 + 0.25 * (len(text) / max(1, len(q))), 3)
        else:
            ratio = SequenceMatcher(None, q, text).ratio()
            q_toks = _tokens(q)
            t_toks = set(_tokens(text))
            overlap = 0
            for tok in q_toks:
                family = _expand(tok)
                if family & t_toks:
                    overlap += 1
            cover = overlap / max(1, len(q_toks))
            score = max(ratio, cover * 0.92)
            if element.type in ("button", "link") and any(t in q for t in ("click", "button", "login", "sign")):
                score = min(1.0, score + 0.03)
            if element.type == "input" and any(t in q for t in ("email", "password", "field", "type", "username")):
                score = min(1.0, score + 0.04)
    if element.source in ("ACCESSIBILITY", "DOM"):
        score = min(1.0, float(score) + 0.08)
    return round(float(score), 3)


def match_elements(query: str, elements: Sequence[ScreenElement]) -> MatchResult:
    q = " ".join((query or "").split())
    ranked = []
    for el in elements:
        s = score_element(q, el)
        if s >= 0.35:
            ranked.append(RankedMatch(element=el, score=s, reason=el.text))
    ranked.sort(key=lambda m: (m.score, len(m.element.text or "")), reverse=True)
    result = MatchResult(query=q, matches=ranked[:6])
    branded = unique_brand_element(q, elements)
    if branded is not None:
        # A unique brand token (microsoft vs odoo) is not ambiguous even if labels look alike.
        preferred = [m for m in ranked if m.element.id == branded.id]
        rest = [m for m in ranked if m.element.id != branded.id]
        result.matches = (preferred + rest)[:6]
        result.ambiguous = False
        return result
    if len(ranked) >= 2 and ranked[0].score >= MEDIUM:
        a, b = ranked[0], ranked[1]
        same_family = SequenceMatcher(None, a.element.text.lower(), b.element.text.lower()).ratio() > 0.45
        loginish = "login" in q.lower() or "sign" in q.lower()
        if loginish and same_family and (a.score - b.score) < 0.12 and b.score >= 0.55:
            result.ambiguous = True
            result.message = (
                f"I found multiple login buttons. Which one do you mean? "
                f"{a.element.text}  ·  {b.element.text}"
            )
        elif (a.score - b.score) < 0.06 and b.score >= 0.70:
            result.ambiguous = True
            result.message = f"I found {len(ranked[:3])} possible matches."
    if result.best and result.band == "low":
        result.message = "I'm not confident which element you mean."
    return result


def is_auto_click(result: MatchResult) -> bool:
    """High-confidence or a unique medium match — safe to click without asking."""
    if not result.best or result.ambiguous:
        return False
    if result.band == "high":
        return True
    if result.band == "medium":
        return len(result.matches) < 2 or result.matches[1].score < result.best.score - 0.12
    return False


def unique_brand_element(query: str, elements: Sequence[ScreenElement]) -> ScreenElement | None:
    wanted = brand_tokens(expand_click_query(query) or query)
    if not wanted:
        return None
    hits = []
    for el in elements:
        toks = set(_tokens(normalize_ocr_query(el.text or "")))
        if wanted <= toks:
            hits.append(el)
    if len(hits) == 1:
        return hits[0]
    return None
