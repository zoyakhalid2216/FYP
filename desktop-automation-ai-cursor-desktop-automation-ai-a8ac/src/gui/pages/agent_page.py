"""AI Agent — plan, confirm, speak, screen understanding."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.screen_view import ScreenView


class AgentPage(QWidget):
    execute_requested = pyqtSignal(str)
    plan_requested = pyqtSignal(str)
    mic_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    suggestion_requested = pyqtSignal(str)
    clarify_chosen = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._plan_data: Dict[str, Any] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(14)

        title = QLabel("AI Desktop Agent")
        title.setObjectName("pageTitle")
        sub = QLabel(
            "Voice or type a goal. DAI looks at the current screen, confirms if unsure, then waits."
        )
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        ask = QFrame()
        ask.setObjectName("panelCard")
        al = QVBoxLayout(ask)
        al.setContentsMargins(18, 16, 18, 16)
        al.setSpacing(10)
        prompt = QLabel("What would you like me to do?")
        prompt.setObjectName("sectionTitle")
        self.command = QLineEdit()
        self.command.setPlaceholderText('Open Chrome, search for today\'s weather, then open the first result')
        self.command.setMinimumHeight(40)
        self.command.returnPressed.connect(self._emit_plan)
        row = QHBoxLayout()
        speak = QPushButton("🎙 Speak")
        speak.setObjectName("btnMicBig")
        speak.clicked.connect(self.mic_requested.emit)
        plan_btn = QPushButton("Explain plan")
        plan_btn.setObjectName("btnSecondary")
        plan_btn.setMinimumHeight(40)
        plan_btn.clicked.connect(self._emit_plan)
        run_btn = QPushButton("Execute")
        run_btn.setObjectName("btnPrimary")
        run_btn.setMinimumHeight(40)
        run_btn.clicked.connect(self._emit_run)
        stop = QPushButton("STOP AUTOMATION")
        stop.setObjectName("btnDanger")
        stop.setMinimumHeight(40)
        stop.clicked.connect(self.stop_requested.emit)
        row.addWidget(speak)
        row.addWidget(plan_btn, 1)
        row.addWidget(run_btn, 1)
        row.addWidget(stop)
        al.addWidget(prompt)
        al.addWidget(self.command)
        al.addLayout(row)
        self.meta = QLabel("Confidence —  ·  Mode: Local AI planner")
        self.meta.setObjectName("pageSubtitle")
        al.addWidget(self.meta)
        root.addWidget(ask)

        self.clarify_box = QFrame()
        self.clarify_box.setObjectName("panelCard")
        cbl = QVBoxLayout(self.clarify_box)
        cbl.setContentsMargins(12, 10, 12, 10)
        cbl.setSpacing(8)
        self.clarify_label = QLabel("Do you mean this?")
        self.clarify_label.setWordWrap(True)
        self.clarify_row = QHBoxLayout()
        self._clarify_buttons: List[QPushButton] = []
        cbl.addWidget(self.clarify_label)
        cbl.addLayout(self.clarify_row)
        self.clarify_box.hide()
        root.addWidget(self.clarify_box)

        chips = QHBoxLayout()
        for text in (
            "Open Chrome",
            "Search YouTube for Python tutorials",
            "Open my Downloads folder",
            "Copy report.pdf to Desktop",
            "Run my study workflow",
        ):
            chip = QPushButton(text)
            chip.setObjectName("btnGhost")
            chip.setCursor(Qt.PointingHandCursor)
            chip.clicked.connect(lambda _=False, t=text: self._use_suggestion(t))
            chips.addWidget(chip)
        chips.addStretch(1)
        root.addLayout(chips)

        mid = QHBoxLayout()
        mid.setSpacing(12)

        plan_card = QFrame()
        plan_card.setObjectName("panelCard")
        pl = QVBoxLayout(plan_card)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.addWidget(self._section("AI PLAN"))
        self.plan_list = QListWidget()
        self.plan_list.setMinimumHeight(220)
        pl.addWidget(self.plan_list, 1)
        self.explain = QTextEdit()
        self.explain.setReadOnly(True)
        self.explain.setMaximumHeight(90)
        self.explain.setPlaceholderText("I’ll explain the plan here before I touch the desktop.")
        pl.addWidget(self.explain)

        vision_card = QFrame()
        vision_card.setObjectName("panelCard")
        vl = QVBoxLayout(vision_card)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.addWidget(self._section("Screen understanding"))
        self.screen = ScreenView()
        vl.addWidget(self.screen, 1)
        self.vision_meta = QLabel("Bounding boxes show what OCR/template matching found.")
        self.vision_meta.setObjectName("pageSubtitle")
        self.vision_meta.setWordWrap(True)
        vl.addWidget(self.vision_meta)

        mid.addWidget(plan_card, 5)
        mid.addWidget(vision_card, 5)
        root.addLayout(mid, 1)

        self.status = QLabel("Ready — type a goal, or say DAI wakeup")
        self.status.setObjectName("pageSubtitle")
        root.addWidget(self.status)
        self.task_log = QLabel("")
        self.task_log.setObjectName("pageSubtitle")
        self.task_log.setWordWrap(True)
        root.addWidget(self.task_log)

        scroll.setWidget(host)
        outer.addWidget(scroll)

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("sectionTitle")
        return lab

    def _use_suggestion(self, text: str) -> None:
        self.command.setText(text)
        self.suggestion_requested.emit(text)
        self.plan_requested.emit(text)

    def _emit_plan(self) -> None:
        text = self.command.text().strip()
        if text:
            self.plan_requested.emit(text)

    def _emit_run(self) -> None:
        text = self.command.text().strip()
        if text:
            self.execute_requested.emit(text)

    def set_command_text(self, text: str) -> None:
        self.command.setText(text)

    def set_status(self, text: str) -> None:
        self.status.setText(text)

    def show_clarify(self, heard: str, suggestions: List[str]) -> None:
        self.clarify_label.setText(
            f'I heard “{heard}”. Do you mean this?'
            if heard
            else "I only caught part of that. Do you mean this?"
        )
        for btn in self._clarify_buttons:
            self.clarify_row.removeWidget(btn)
            btn.deleteLater()
        self._clarify_buttons = []
        for text in (suggestions or [])[:4]:
            btn = QPushButton(text)
            btn.setObjectName("btnGhost")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=text: self.clarify_chosen.emit(t))
            self.clarify_row.addWidget(btn)
            self._clarify_buttons.append(btn)
        self.clarify_box.setVisible(bool(self._clarify_buttons))

    def set_task_history(self, lines: List[str]) -> None:
        self.task_log.setText("\n".join(lines or []))

    def clear_clarify(self) -> None:
        for btn in self._clarify_buttons:
            self.clarify_row.removeWidget(btn)
            btn.deleteLater()
        self._clarify_buttons = []
        self.clarify_box.hide()

    def show_plan(self, plan: Dict[str, Any]) -> None:
        self._plan_data = plan or {}
        self.plan_list.clear()
        conf = int(float(plan.get("confidence") or 0) * 100)
        mode = plan.get("mode") or "local"
        est = plan.get("estimated_s") or 0
        self.meta.setText(
            f"Intent: {plan.get('intent') or '—'}   ·   Confidence {conf}%   ·   "
            f"~{est:.0f}s   ·   Mode: {mode} planner"
        )
        lines = [
            f"I understood your request as: {plan.get('summary') or ''}",
            f"Estimated execution time: ~{est:.0f} seconds.",
        ]
        if plan.get("needs_clarification"):
            lines.append("⚠ I’m not completely sure — review the plan or pick a suggestion.")
        if plan.get("suggestions") and plan.get("needs_clarification"):
            lines.append("Did you mean: " + "  ·  ".join(plan.get("suggestions")[:4]))
        self.explain.setPlainText("\n".join(lines))
        for step in plan.get("steps") or []:
            mark = {"done": "✓", "running": "●", "failed": "✕"}.get(step.get("status"), "○")
            item = QListWidgetItem(f"{mark}  {step.get('title')}")
            self.plan_list.addItem(item)

    def mark_status(self, message: str) -> None:
        self.status.setText(message)
        # Tick matching running/done lines from live status prefixes
        text = message.strip()
        prefix = ""
        title = text
        if text.startswith("✓ "):
            prefix, title = "✓", text[2:]
        elif text.startswith("● "):
            prefix, title = "●", text[2:]
        elif text.startswith("⚠ "):
            prefix, title = "⚠", text[2:]
        if not prefix:
            return
        for i in range(self.plan_list.count()):
            item = self.plan_list.item(i)
            raw = item.text()[2:].strip() if len(item.text()) > 2 else item.text()
            if raw == title or title.startswith(raw) or raw.startswith(title):
                item.setText(f"{prefix}  {raw}")
                break

    def show_vision(self, frame=None, boxes: Optional[List[Dict[str, Any]]] = None, path: str = "") -> None:
        self.screen.set_frame(frame, boxes=boxes, path=path)
        n = len(boxes or [])
        self.vision_meta.setText(
            f"{n} detected region(s). Purple boxes are OCR/template matches."
            if n
            else "No elements boxed yet — run a click or inspect step."
        )
