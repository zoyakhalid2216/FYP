"""Voice Command screen — compact, scrollable, no overlap."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSlider,
    QScrollArea,
    QSizePolicy,
)

from src.gui.components.logs_widget import LogsWidget


class VoiceCommandPage(QWidget):
    execute_requested = pyqtSignal(str)
    mic_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    rerun_requested = pyqtSignal(str)
    sensitivity_changed = pyqtSignal(float)
    stop_requested = pyqtSignal()
    show_dai_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recent_bound = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QHBoxLayout(host)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(8)

        head = QHBoxLayout()
        titles = QVBoxLayout()
        t = QLabel("Voice Command")
        t.setObjectName("pageTitle")
        s = QLabel(
            "AI uses the Google/Chrome mic. Say “AI”, then speak your "
            "steps. AI looks at the current screen, confirms only when unsure, "
            "and waits for the next command. Say “done” or “AI sleep” to finish. "
            "Hotkey: Ctrl+Space"
        )
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles, 1)
        self.last_lbl = QLabel("Last: —")
        self.last_lbl.setObjectName("pageSubtitle")
        self.last_lbl.setWordWrap(True)
        self.last_lbl.setMaximumWidth(220)
        head.addWidget(self.last_lbl, 0, Qt.AlignTop)
        left.addLayout(head)

        panel = QFrame()
        panel.setObjectName("voicePanel")
        pl = QVBoxLayout(panel)
        pl.setContentsMargins(16, 14, 16, 14)
        pl.setSpacing(8)

        self.status = QLabel("✓ Ready — Speak or type a command")
        self.status.setStyleSheet("font-weight:700;font-size:13px;")
        self.status.setWordWrap(True)
        self.status.setAlignment(Qt.AlignCenter)

        hint = QLabel(
            "AI · Open Chrome · Click Login · What’s next? · done"
        )
        hint.setObjectName("pageSubtitle")
        hint.setAlignment(Qt.AlignCenter)
        hint.setWordWrap(True)

        mic_row = QHBoxLayout()
        mic_row.addStretch()
        self.btn_mic = QPushButton("🎙 Speak")
        self.btn_mic.setObjectName("btnMicBig")
        self.btn_mic.setToolTip(
            "Opens Chrome or Edge — allow the microphone, then speak. No extra library needed."
        )
        self.btn_mic.clicked.connect(self.mic_requested.emit)
        mic_row.addWidget(self.btn_mic)
        mic_row.addStretch()

        self.command = QLineEdit()
        self.command.setPlaceholderText("Open any file, app, or folder…")
        self.command.returnPressed.connect(self._emit_execute)

        actions = QHBoxLayout()
        clear = QPushButton("Clear")
        clear.setObjectName("btnGhost")
        clear.clicked.connect(self._clear)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btnDanger")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        run = QPushButton("▶ Execute")
        run.clicked.connect(self._emit_execute)
        actions.addWidget(clear)
        actions.addWidget(self.btn_stop)
        actions.addStretch()
        actions.addWidget(run)

        pl.addWidget(self.status)
        pl.addWidget(hint)
        pl.addLayout(mic_row)
        pl.addWidget(self.command)
        pl.addLayout(actions)
        left.addWidget(panel)

        recent_title = QLabel("Recent")
        recent_title.setStyleSheet("font-weight:700;font-size:12px;")
        left.addWidget(recent_title)
        self.recent = QListWidget()
        self.recent.setMaximumHeight(110)
        self.recent.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        left.addWidget(self.recent)

        self.console = LogsWidget()
        self.console.setMinimumHeight(120)
        self.console.setMaximumHeight(180)
        left.addWidget(self.console)
        left.addStretch(1)

        right = QFrame()
        right.setObjectName("panelCard")
        right.setFixedWidth(220)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(12, 12, 12, 12)
        rl.setSpacing(6)
        rl.addWidget(QLabel("Quick actions"))
        for label, cmd in (
            ("Open Chrome", "Open chrome"),
            ("Open Downloads", "Open folder Downloads"),
            ("Copy file → Desktop", "Copy file report to Desktop"),
            ("Run a workflow", "Run Morning Setup"),
            ("Search Google", "Search latest AI news"),
            ("Click Login", "Click Login"),
        ):
            b = QPushButton(label)
            b.setObjectName("btnSecondary")
            b.clicked.connect(lambda _=False, c=cmd: self._suggest(c))
            rl.addWidget(b)

        rl.addSpacing(6)
        rl.addWidget(QLabel("Mic sensitivity"))
        self.sensitivity = QSlider(Qt.Horizontal)
        self.sensitivity.setRange(10, 100)
        self.sensitivity.setValue(70)
        self.sensitivity.valueChanged.connect(
            lambda v: self.sensitivity_changed.emit(v / 100.0)
        )
        rl.addWidget(self.sensitivity)
        self.conf_lbl = QLabel("Engine: AI Google mic — say AI")
        self.conf_lbl.setObjectName("pageSubtitle")
        self.conf_lbl.setWordWrap(True)
        rl.addWidget(self.conf_lbl)
        show_dai = QPushButton("Show AI window")
        show_dai.setObjectName("btnSecondary")
        show_dai.clicked.connect(self.show_dai_requested.emit)
        rl.addWidget(show_dai)
        rl.addStretch()
        foot = QLabel("v0.4.0")
        foot.setObjectName("footerLabel")
        rl.addWidget(foot)

        root.addLayout(left, 1)
        root.addWidget(right, 0)
        scroll.setWidget(host)
        outer.addWidget(scroll)

    def _emit_execute(self) -> None:
        text = self.command.text().strip()
        if text:
            self.execute_requested.emit(text)

    def _clear(self) -> None:
        self.command.clear()
        self.clear_requested.emit()

    def _suggest(self, cmd: str) -> None:
        self.command.setText(cmd)

    def set_listening(self, listening: bool) -> None:
        self.status.setText(
            "● Listening… speak now" if listening else "✓ Ready — Speak or type a command"
        )
        self.btn_mic.setEnabled(not listening)
        self.btn_mic.setText("…" if listening else "🎙 Speak")

    def set_busy(self, busy: bool) -> None:
        self.btn_stop.setEnabled(busy)
        self.btn_mic.setEnabled(not busy)

    def set_command_text(self, text: str) -> None:
        self.command.setText(text)
        self.command.setFocus()
        self.command.selectAll()

    def set_status_message(self, message: str) -> None:
        self.status.setText(message)
        level = "info"
        low = message.lower()
        if message.startswith("✓") or "success" in low or "done" in low:
            level = "success"
        elif message.startswith("✗") or "error" in low or "fail" in low:
            level = "error"
        elif message.startswith("●"):
            level = "warn"
        self.console.append(message, level=level)

    def focus_command(self) -> None:
        self.command.setFocus()
        self.command.selectAll()

    def set_engine_label(self, text: str) -> None:
        self.conf_lbl.setText(text)

    def update_recent(
        self, commands: List[Dict[str, Any]], logs_by_cmd: Dict[int, str] | None = None
    ) -> None:
        self.recent.clear()
        logs_by_cmd = logs_by_cmd or {}
        if commands:
            self.last_lbl.setText(f"Last: {commands[0].get('executed_at', '—')}")
        for cmd in commands[:8]:
            status = logs_by_cmd.get(cmd.get("command_id"), "—")
            text = f"{cmd.get('raw_text', '')}  ·  {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, cmd.get("raw_text", ""))
            self.recent.addItem(item)
        if not self._recent_bound:
            self.recent.itemDoubleClicked.connect(
                lambda it: self.rerun_requested.emit(it.data(Qt.UserRole) or "")
            )
            self._recent_bound = True
