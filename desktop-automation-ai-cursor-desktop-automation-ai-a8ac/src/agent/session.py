"""Interactive task session — keep listening after each step until the user says done."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

IDLE = "IDLE"
LISTENING = "LISTENING"
EXECUTING = "EXECUTING"
WAITING_FOR_USER = "WAITING_FOR_USER"
WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
ANALYZING_SCREEN = "ANALYZING_SCREEN"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
CANCELLED = "CANCELLED"


@dataclass
class TaskStep:
    text: str
    ok: bool = True
    at: float = field(default_factory=time.time)


@dataclass
class PendingConfirm:
    kind: str
    prompt: str
    spoken: str = ""
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    action: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskSession:
    task_id: str
    goal: str = ""
    status: str = LISTENING
    steps: List[TaskStep] = field(default_factory=list)
    last_elements: List[Dict[str, Any]] = field(default_factory=list)
    last_target: Dict[str, Any] = field(default_factory=dict)
    pending: Optional[PendingConfirm] = None
    application: str = ""
    url: str = ""
    created_at: float = field(default_factory=time.time)

    def history_lines(self) -> List[str]:
        lines = []
        if self.goal:
            lines.append(f"Task: {self.goal}")
        for step in self.steps[-12:]:
            mark = "✓" if step.ok else "✕"
            lines.append(f"{mark} {step.text}")
        if self.status == WAITING_FOR_USER:
            lines.append("Current: Waiting for next instruction.")
        elif self.status == WAITING_FOR_CONFIRMATION and self.pending:
            lines.append(f"Current: {self.pending.prompt}")
        return lines

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "status": self.status,
            "steps": [{"text": s.text, "ok": s.ok} for s in self.steps],
            "application": self.application,
            "url": self.url,
        }


class TaskManager:
    def __init__(self) -> None:
        self.session: Optional[TaskSession] = None

    @property
    def active(self) -> bool:
        if self.session is None:
            return False
        return self.session.status not in (IDLE, COMPLETED, FAILED, CANCELLED)

    def ensure(self, goal: str = "") -> TaskSession:
        if not self.active:
            self.session = TaskSession(task_id=str(uuid.uuid4())[:8], goal=goal, status=LISTENING)
        elif goal and not self.session.goal:
            self.session.goal = goal
        return self.session

    def start(self, goal: str) -> TaskSession:
        self.session = TaskSession(task_id=str(uuid.uuid4())[:8], goal=goal, status=WAITING_FOR_USER)
        self.record("Started interactive task", ok=True)
        return self.session

    def record(self, text: str, *, ok: bool = True) -> None:
        if not self.session:
            return
        self.session.steps.append(TaskStep(text=text, ok=ok))

    def set_status(self, status: str) -> None:
        if self.session:
            self.session.status = status

    def set_screen(self, elements: List[Dict[str, Any]], *, url: str = "", application: str = "") -> None:
        if not self.session:
            return
        self.session.last_elements = list(elements or [])
        if url:
            self.session.url = url
        if application:
            self.session.application = application

    def set_pending(self, pending: Optional[PendingConfirm]) -> None:
        if not self.session:
            self.ensure()
        self.session.pending = pending
        self.session.status = WAITING_FOR_CONFIRMATION if pending else WAITING_FOR_USER

    def waiting_for_next(self) -> None:
        if self.session:
            self.session.pending = None
            self.session.status = WAITING_FOR_USER

    def complete(self, reason: str = "Task completed.") -> None:
        if self.session:
            self.record(reason, ok=True)
            self.session.status = COMPLETED
            self.session.pending = None

    def cancel(self, reason: str = "Cancelled.") -> None:
        if self.session:
            self.record(reason, ok=False)
            self.session.status = CANCELLED
            self.session.pending = None

    def resolve_reference(self, text: str) -> Optional[Dict[str, Any]]:
        t = (text or "").lower().strip()
        sess = self.session
        if not sess:
            return None
        if t in ("it", "that", "this", "the same", "click it", "click that", "click this"):
            return sess.last_target or (sess.last_elements[0] if sess.last_elements else None)
        if t in ("the second one", "second one", "the other one", "the other button"):
            if len(sess.last_elements) >= 2:
                return sess.last_elements[1]
            if sess.pending and len(sess.pending.candidates) >= 2:
                return sess.pending.candidates[1]
        if t in ("the first one", "first one"):
            if sess.last_elements:
                return sess.last_elements[0]
            if sess.pending and sess.pending.candidates:
                return sess.pending.candidates[0]
        return None
