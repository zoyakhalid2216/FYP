"""AI Command Planner: NLP parse → intent, entities, action plan, confidence."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from src.nlp.engine import ParsedCommand, _fill_empty_clicks_after_search
from src.vision.search_result import (
    FIRST_RESULT_ELEMENT,
    first_result_entities,
    is_first_result_phrase,
    parse_result_index,
    ranked_result_entities,
)

SUGGESTIONS = [
    "Open Chrome",
    "Open Chrome and search for FYP ideas",
    "Search YouTube for Python tutorials",
    "Open my Downloads folder",
    "Copy report.pdf to Desktop",
    "Run Morning Study Setup",
    "Click Login",
    "Type hello",
]


def _title_for(intent: str, entities: Dict[str, Any]) -> str:
    app = str(entities.get("app") or entities.get("query") or "").strip()
    element = str(entities.get("element") or "").strip()
    text = str(entities.get("text") or "").strip()
    query = str(entities.get("query") or "").strip()
    seconds = entities.get("seconds", 1)
    if intent == "open_app":
        return f"Open {app or 'application'}"
    if intent == "open_file":
        return f"Open {query or app or 'file / folder'}"
    if intent == "search_web":
        return f'Search Google for “{query}”' if query else "Search the web"
    if intent in ("click_text", "click_button"):
        idx = int(entities.get("result_index") or 0) or (
            1
            if is_first_result_phrase(element) or element == FIRST_RESULT_ELEMENT
            else 0
        )
        if idx:
            ordinal = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(idx, str(idx))
            return f"Click the {ordinal} search result"
        return f'Click “{element or "target"}” on screen'
    if intent == "type_text":
        shown = text if len(text) < 40 else text[:37] + "…"
        return f'Type “{shown}”' if shown else "Type text"
    if intent == "fill_form":
        return f'Fill {entities.get("field") or "field"} with “{text}”'
    if intent == "press_key":
        return f'Press {entities.get("key") or "enter"}'
    if intent == "scroll":
        return f"Scroll {entities.get('direction') or 'down'}"
    if intent == "wait":
        return f"Wait {seconds} second(s) for the UI"
    if intent == "copy_file":
        return f"Copy {entities.get('source') or 'file'} → {entities.get('destination') or 'destination'}"
    if intent == "move_file":
        return f"Move {entities.get('source') or 'file'} → {entities.get('destination') or 'destination'}"
    if intent == "run_workflow":
        return f"Run workflow “{entities.get('workflow') or ''}”"
    if intent == "close_app":
        target = "the active window" if app == "__focused__" else (app or "application")
        return f"Close {target}"
    if intent == "close_tab":
        return "Close current tab"
    if intent == "minimize_window":
        target = f"{app} window" if app and app != "__focused__" else "window"
        return f"Minimize {target}"
    if intent == "restore_window":
        target = f"{app} window" if app and app != "__focused__" else "window"
        return f"Restore {target}"
    if intent == "inspect_screen":
        return "Inspect screen (OCR / vision)"
    if intent == "verify_screen":
        return "Verify the screen changed"
    return intent.replace("_", " ").title()


def _estimate(intent: str, entities: Dict[str, Any]) -> float:
    if intent == "wait":
        try:
            return float(entities.get("seconds") or 1)
        except (TypeError, ValueError):
            return 1.0
    if intent in ("open_app", "open_file", "search_web"):
        return 1.6
    if intent in ("click_text", "click_button", "inspect_screen", "verify_screen"):
        return 1.1
    if intent in ("close_app", "close_tab", "minimize_window", "restore_window"):
        return 0.8
    if intent in ("copy_file", "move_file"):
        return 0.8
    return 0.6


@dataclass
class PlanStep:
    key: str
    title: str
    intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    kind: str = "action"  # action | wait | inspect | verify
    estimate_s: float = 0.8
    status: str = "pending"
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ActionPlan:
    raw_text: str
    intent: str
    confidence: float
    summary: str
    steps: List[PlanStep] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    mode: str = "local"
    estimated_s: float = 0.0
    needs_clarification: bool = False
    parsed: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() if isinstance(s, PlanStep) else s for s in self.steps]
        return data

    def executable_intents(self) -> List[str]:
        return [s.intent for s in self.steps if s.kind in ("action", "wait")]


class CommandPlanner:
    """Turn a parsed command into a defensible multi-step AI action plan."""

    def __init__(self, *, mode: str = "local", min_confidence: float = 0.45) -> None:
        self.mode = "enhanced" if str(mode).lower() in ("enhanced", "cloud", "ai") else "local"
        self.min_confidence = float(min_confidence)

    def plan(self, parsed: ParsedCommand, raw_text: str = "") -> ActionPlan:
        raw = (raw_text or parsed.raw_text or "").strip()
        steps = self._expand(parsed, raw)
        confidence = float(parsed.confidence or 0.0)
        unknown = parsed.intent == "unknown" or not steps
        suggestions = suggest_commands(raw) if unknown or confidence < self.min_confidence else []
        if unknown and not any(s.intent != "unknown" for s in steps):
            summary = "I could not fully understand that goal."
            return ActionPlan(
                raw_text=raw,
                intent="unknown",
                confidence=confidence,
                summary=summary,
                steps=[],
                suggestions=suggestions or SUGGESTIONS[:5],
                mode=self.mode,
                estimated_s=0.0,
                needs_clarification=True,
                parsed=parsed.to_dict(),
            )
        estimated = round(sum(s.estimate_s for s in steps), 1)
        n = len(steps)
        summary = (
            f"Multi-step automation ({n} steps)"
            if n > 1
            else (steps[0].title if steps else parsed.intent)
        )
        return ActionPlan(
            raw_text=raw,
            intent=parsed.intent,
            confidence=confidence,
            summary=summary,
            steps=steps,
            suggestions=suggestions,
            mode=self.mode,
            estimated_s=estimated,
            needs_clarification=confidence < self.min_confidence,
            parsed=parsed.to_dict(),
        )

    def _expand(self, parsed: ParsedCommand, raw: str) -> List[PlanStep]:
        source = parsed.steps or [
            {
                "intent": parsed.intent,
                "entities": parsed.entities or {},
                "confidence": parsed.confidence,
            }
        ]
        source = _fill_empty_clicks_after_search(
            [s for s in source if s.get("intent") and s.get("intent") != "unknown"]
        )
        planned: List[PlanStep] = []
        idx = 0

        def add(intent: str, entities: Optional[Dict[str, Any]] = None, kind: str = "action") -> None:
            nonlocal idx
            idx += 1
            ent = dict(entities or {})
            planned.append(
                PlanStep(
                    key=f"s{idx}",
                    title=_title_for(intent, ent),
                    intent=intent,
                    entities=ent,
                    kind=kind,
                    estimate_s=_estimate(intent, ent),
                )
            )

        for step in source:
            intent = str(step.get("intent") or "")
            entities = dict(step.get("entities") or {})
            if intent in ("click_text", "click_button"):
                el = str(entities.get("element") or "").strip()
                if not el and not entities.get("first_result"):
                    if any(s.get("intent") == "search_web" for s in source):
                        entities.update(first_result_entities())
                    else:
                        continue
                add("inspect_screen", {"element": entities.get("element", "")}, kind="inspect")
                add(intent, entities, kind="action")
                add("verify_screen", {"expect": "ui_changed"}, kind="verify")
                continue
            add(intent, entities, kind="wait" if intent == "wait" else "action")
            if intent in ("open_app", "open_file"):
                next_is_wait = False
                add("wait", {"seconds": 1}, kind="wait")
                _ = next_is_wait
            elif intent == "search_web":
                add("wait", {"seconds": 1.2}, kind="wait")
                add("inspect_screen", {"element": entities.get("query", "")}, kind="inspect")

        lower = raw.lower()
        has_search = any(s.intent == "search_web" for s in planned)
        has_click = any(s.intent in ("click_text", "click_button") for s in planned)
        has_ranked = any(
            int(s.entities.get("result_index") or 0)
            or s.entities.get("first_result")
            or is_first_result_phrase(str(s.entities.get("element") or ""))
            for s in planned
        )
        spoken_idx = parse_result_index(raw)
        if has_search and not has_ranked:
            if spoken_idx:
                add("inspect_screen", ranked_result_entities(spoken_idx), kind="inspect")
                add("click_text", ranked_result_entities(spoken_idx), kind="action")
                add("verify_screen", {"expect": "page_changed"}, kind="verify")
            elif not has_click and re.search(r"\b(click|tap)\b", lower):
                add("inspect_screen", first_result_entities(), kind="inspect")
                add("click_text", first_result_entities(), kind="action")
                add("verify_screen", {"expect": "page_changed"}, kind="verify")

        # Collapse consecutive duplicate waits
        cleaned: List[PlanStep] = []
        for step in planned:
            if (
                step.intent == "wait"
                and cleaned
                and cleaned[-1].intent == "wait"
            ):
                continue
            cleaned.append(step)
        # Re-number keys
        for i, step in enumerate(cleaned, start=1):
            step.key = f"s{i}"
        return cleaned


def suggest_commands(text: str) -> List[str]:
    t = (text or "").lower()
    scored: List[tuple] = []
    for item in SUGGESTIONS:
        words = [w for w in re.split(r"\W+", item.lower()) if w]
        hits = sum(1 for w in words if w in t)
        scored.append((hits, item))
    scored.sort(key=lambda x: -x[0])
    picked = [s for hits, s in scored if hits][:4]
    if len(picked) < 3:
        for item in SUGGESTIONS:
            if item not in picked:
                picked.append(item)
            if len(picked) >= 4:
                break
    return picked
