"""Command input, mic control, and run settings."""

from __future__ import annotations

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QFormLayout,
    QDoubleSpinBox,
)


class ControlsWidget(QWidget):
    start_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    mic_requested = pyqtSignal()
    capture_requested = pyqtSignal()
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        title = QLabel("Command center")
        title.setStyleSheet("font-weight: 700; color: #0f3d4c; font-size: 14px;")
        hint = QLabel('Try: "Open Chrome and search weather"')
        hint.setObjectName("sectionHint")

        cmd_row = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("Type a command in plain English…")
        self.command_input.returnPressed.connect(self._emit_start)
        self.btn_mic = QPushButton("Mic")
        self.btn_mic.setObjectName("btnMic")
        self.btn_mic.setToolTip("Speak a command")
        self.btn_mic.clicked.connect(self.mic_requested.emit)
        cmd_row.addWidget(self.command_input, stretch=1)
        cmd_row.addWidget(self.btn_mic)

        btn_row = QHBoxLayout()
        self.btn_start = QPushButton("Run command")
        self.btn_start.clicked.connect(self._emit_start)
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.setObjectName("btnDanger")
        self.btn_stop.clicked.connect(self.stop_requested.emit)
        self.btn_stop.setEnabled(False)
        self.btn_capture = QPushButton("Capture screen")
        self.btn_capture.setObjectName("btnSecondary")
        self.btn_capture.clicked.connect(self.capture_requested.emit)
        btn_row.addWidget(self.btn_start)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_capture)

        settings = QGroupBox("Safety & settings")
        form = QFormLayout(settings)
        self.chk_dry_run = QCheckBox("Dry-run (safe mode — no real mouse/keyboard)")
        self.chk_dry_run.setChecked(True)
        self.chk_failsafe = QCheckBox("Fail-safe (move mouse to corner to abort)")
        self.chk_failsafe.setChecked(True)
        self.spin_pause = QDoubleSpinBox()
        self.spin_pause.setRange(0.05, 3.0)
        self.spin_pause.setSingleStep(0.05)
        self.spin_pause.setValue(0.35)
        form.addRow(self.chk_dry_run)
        form.addRow(self.chk_failsafe)
        form.addRow("Action pause (sec)", self.spin_pause)

        self.chk_dry_run.stateChanged.connect(self._emit_settings)
        self.chk_failsafe.stateChanged.connect(self._emit_settings)
        self.spin_pause.valueChanged.connect(self._emit_settings)

        self.status_line = QLabel("Ready")
        self.status_line.setObjectName("sectionHint")

        root.addWidget(title)
        root.addWidget(hint)
        root.addLayout(cmd_row)
        root.addLayout(btn_row)
        root.addWidget(settings)
        root.addWidget(self.status_line)
        root.addStretch(1)

    def _emit_start(self) -> None:
        text = self.command_input.text().strip()
        if text:
            self.start_requested.emit(text)

    def _emit_settings(self) -> None:
        self.settings_changed.emit(
            {
                "dry_run": self.chk_dry_run.isChecked(),
                "failsafe": self.chk_failsafe.isChecked(),
                "pause_seconds": float(self.spin_pause.value()),
            }
        )

    def set_running(self, running: bool) -> None:
        self.btn_start.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.command_input.setEnabled(not running)

    def set_listening(self, listening: bool) -> None:
        self.btn_mic.setProperty("listening", "true" if listening else "false")
        self.btn_mic.style().unpolish(self.btn_mic)
        self.btn_mic.style().polish(self.btn_mic)
        self.btn_mic.setText("…" if listening else "Mic")

    def set_status(self, message: str) -> None:
        self.status_line.setText(message)

    def set_command_text(self, text: str) -> None:
        self.command_input.setText(text)

    def apply_user_conf(self, conf: dict) -> None:
        self.chk_dry_run.setChecked(bool(conf.get("dry_run", 1)))
        self.chk_failsafe.setChecked(bool(conf.get("failsafe", 1)))
        self.spin_pause.setValue(float(conf.get("pause_seconds", 0.35)))
