"""Hybrid click-target resolver: accessibility → OCR → vision, then brand fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Set

from src.agent.a11y import collect_elements as collect_a11y
from src.agent.analyzer import ScreenAnalyzer
from src.agent.elements import ScreenElement, ScreenState
from src.agent.matcher import is_auto_click, match_elements, unique_brand_element
from src.agent.semantic import expand_click_query


@dataclass
class ResolveResult:
    query: str
    expanded: str
    element: Optional[ScreenElement] = None
    method: str = ""
    score: float = 0.0
    matches: list = field(default_factory=list)
    ambiguous: bool = False
    message: str = ""
    state: Optional[ScreenState] = None
    strategies: List[str] = field(default_factory=list)
    candidates: List[ScreenElement] = field(default_factory=list)
    weak: bool = False


def rank_targets(query: str, elements: Sequence[ScreenElement]) -> ResolveResult:
    """Pure ranking used by tests and by the live resolver."""
    expanded = expand_click_query(query)
    out = ResolveResult(query=query, expanded=expanded)
    ranked = match_elements(expanded, elements)
    out.matches = ranked.matches
    out.candidates = [m.element for m in ranked.matches]
    if ranked.ambiguous:
        out.ambiguous = True
        out.message = ranked.message
        out.element = ranked.best.element if ranked.best else None
        out.score = ranked.confidence
        out.method = _method_for(out.element)
        return out
    if is_auto_click(ranked) and ranked.best:
        out.element = ranked.best.element
        out.score = ranked.best.score
        out.method = _method_for(out.element)
        return out
    branded = unique_brand_element(expanded, elements)
    if branded is None and expanded != (query or "").strip():
        branded = unique_brand_element(query, elements)
    if branded is not None:
        out.element = branded
        out.score = 0.93
        out.method = _method_for(branded) or "brand"
        return out
    if ranked.best:
        out.element = ranked.best.element
        out.score = ranked.best.score
        out.method = _method_for(out.element)
        out.weak = True
        out.message = ranked.message
    return out


def resolve_click_target(
    query: str,
    vision: Any,
    frame=None,
    *,
    exclude_ids: Optional[Set[str]] = None,
) -> ResolveResult:
    """Try accessibility, then the OCR screen model, then vision.locate."""
    expanded = expand_click_query(query)
    skip = exclude_ids or set()
    out = ResolveResult(query=query, expanded=expanded)
    a11y: List[ScreenElement] = []

    out.strategies.append("accessibility")
    try:
        a11y = [e for e in collect_a11y(getattr(vision, "last_region", None)) if e.id not in skip]
    except Exception:
        a11y = []
    if a11y:
        ranked = rank_targets(expanded, a11y)
        out.strategies[-1] = "accessibility"
        if ranked.element and not ranked.weak and not ranked.ambiguous:
            ranked.strategies = list(out.strategies)
            ranked.state = out.state
            return ranked
        if ranked.ambiguous:
            ranked.strategies = list(out.strategies)
            return ranked

    out.strategies.append("ocr")
    state = None
    try:
        state = ScreenAnalyzer(vision).analyze(frame, extra_elements=a11y, include_accessibility=False)
        out.state = state
        live = [e for e in state.elements if e.id not in skip]
        ranked = rank_targets(expanded, live)
        out.matches = ranked.matches
        out.candidates = ranked.candidates
        if ranked.ambiguous:
            ranked.strategies = list(out.strategies)
            ranked.state = state
            return ranked
        if ranked.element and not ranked.weak:
            ranked.strategies = list(out.strategies)
            ranked.state = state
            return ranked
        if ranked.element:
            out.element = ranked.element
            out.score = ranked.score
            out.method = ranked.method
            out.weak = True
    except Exception:
        state = out.state

    out.strategies.append("vision")
    if vision is not None and hasattr(vision, "locate") and (expanded or query):
        try:
            det = vision.locate(expanded or query, prefer="ocr", frame=frame)
        except Exception:
            det = None
        if det is not None and getattr(det, "found", False):
            el = ScreenElement(
                id=f"vision-{int(det.x)}-{int(det.y)}",
                type="button",
                text=str(det.label or expanded or query),
                role="vision",
                x=max(0, int(det.x) - int(det.width or 8) // 2),
                y=max(0, int(det.y) - int(det.height or 8) // 2),
                width=max(8, int(det.width or 8)),
                height=max(8, int(det.height or 8)),
                confidence=float(det.confidence or 0.8),
                source="VISION",
            )
            if el.id not in skip:
                out.element = el
                out.method = "vision"
                out.score = max(float(det.confidence or 0.8), 0.8)
                out.weak = False
                out.candidates = [el] + [c for c in out.candidates if c.id != el.id]
                return out

    if out.element is None and state is not None:
        branded = unique_brand_element(expanded, [e for e in state.elements if e.id not in skip])
        if branded is not None:
            out.element = branded
            out.method = "brand"
            out.score = 0.9
            out.weak = False
    return out


def visible_loginish(elements: Sequence[ScreenElement]) -> List[dict]:
    rows = []
    for e in elements:
        if re.search(
            r"login|sign|microsoft|odoo|next|submit|email|password",
            e.text or "",
            re.I,
        ):
            rows.append(
                {
                    "text": e.text,
                    "score": 0.5,
                    "x": e.x,
                    "y": e.y,
                    "width": e.width,
                    "height": e.height,
                }
            )
        if len(rows) >= 4:
            break
    return rows


def _method_for(element: Optional[ScreenElement]) -> str:
    if element is None:
        return ""
    src = str(element.source or "ocr").lower()
    if src == "accessibility":
        return "accessibility"
    if src == "dom":
        return "dom"
    if src == "vision":
        return "vision"
    return src or "ocr"
