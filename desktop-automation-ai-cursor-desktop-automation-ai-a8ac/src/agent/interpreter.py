"""Turn finalized speech into structured actions. Partials never reach here."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from src.agent.actions import ComputerAction, intent_to_action
from src.agent.normalize import is_final_transcript, normalize_command
from src.agent.session import TaskManager
from src.nlp.engine import NLPEngine
from src.speech.wake import clean_spoken_command

_TASK_START = re.compile(
    r"\b(help me|log me in|log into|login to|walk me through|start (a |the )?task)\b",
    re.I,
)
_TASK_END = re.compile(r"^(done|finish(ed)?|that's all|thats all|end task|complete)$", re.I)
_STOP = re.compile(r"^((dai|ai)\s+)?stop(\s+now)?$|^cancel( task)?$|^emergency stop$", re.I)
_GO_URL = re.compile(
    r"\b(?:go to|open|visit|navigate(?: to)?|search)\s+(?:https?://)?(?P<host>[\w.-]+\.[\w.-]+)\b",
    re.I,
)
_REF = re.compile(
    r"^(click|tap)?\s*(it|that|this|the same( thing)?|the (first|second|other) one)$",
    re.I,
)


@dataclass
class InterpretResult:
    actions: List[ComputerAction] = field(default_factory=list)
    spoken: str = ""
    normalized: str = ""
    start_task: bool = False
    end_task: bool = False
    stop: bool = False
    reference: Optional[str] = None
    ask: str = ""


class CommandInterpreter:
    def __init__(self, nlp: Optional[NLPEngine] = None) -> None:
        self.nlp = nlp or NLPEngine(lazy=True)

    def interpret(
        self,
        text: str,
        *,
        is_final: bool = True,
        tasks: Optional[TaskManager] = None,
    ) -> InterpretResult:
        if not is_final_transcript(is_final=is_final):
            return InterpretResult(spoken=text or "", ask="partial")
        raw = clean_spoken_command(normalize_command(text))
        result = InterpretResult(spoken=text or "", normalized=raw)
        if not raw:
            return result
        if _STOP.match(raw):
            result.stop = True
            result.actions.append(ComputerAction(type="STOP", spoken=raw, confidence=0.99))
            return result
        if _TASK_END.match(raw):
            result.end_task = True
            result.actions.append(ComputerAction(type="END_TASK", spoken=raw, confidence=0.99))
            return result
        if _TASK_START.search(raw) and not re.search(r"\b(click|type|open chrome|go to)\b", raw):
            result.start_task = True
            result.actions.append(
                ComputerAction(type="START_TASK", parameters={"goal": raw}, spoken=raw, confidence=0.9)
            )
            return result
        if _REF.match(raw) and tasks is not None:
            result.reference = raw
            hit = tasks.resolve_reference(raw)
            if hit:
                result.actions.append(
                    ComputerAction(type="CLICK", target=hit, parameters=hit, spoken=raw, confidence=0.8)
                )
                return result
        host = _GO_URL.search(raw)
        if host and not re.search(r"\bclick\b", raw):
            url = host.group("host").strip().rstrip(".")
            if not url.startswith("http"):
                url = "https://" + url
            result.actions.append(
                ComputerAction(type="OPEN_URL", parameters={"url": url}, spoken=raw, confidence=0.93)
            )
            return result

        parsed = self.nlp.parse(raw)
        for step in parsed.steps or [
            {"intent": parsed.intent, "entities": parsed.entities, "confidence": parsed.confidence}
        ]:
            action = intent_to_action(
                str(step.get("intent") or parsed.intent),
                dict(step.get("entities") or parsed.entities or {}),
                confidence=float(step.get("confidence") or parsed.confidence or 0),
                spoken=raw,
            )
            if action:
                result.actions.append(action)
        if _TASK_START.search(raw) and result.actions:
            result.start_task = True
        return result
