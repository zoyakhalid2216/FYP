"""Tiny always-on-top DAI listener on the desktop."""

from __future__ import annotations

from typing import List, Sequence

from PyQt5.QtCore import Qt, QPoint, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


class DaiOverlay(QWidget):
    close_requested = pyqtSignal()
    retry_requested = pyqtSignal()
    tap_requested = pyqtSignal()
    confirm_requested = pyqtSignal(str)
    stop_requested = pyqtSignal()
    yes_requested = pyqtSignal()
    no_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("daiOverlay")
        self.setWindowTitle("AI")
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFixedSize(312, 168)
        self._drag: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._hidden_for_action = False
        self._clarifying = False
        self._element_confirm = False
        self._chip_buttons: List[QPushButton] = []
        self._agent_name = "AI"

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        top = QHBoxLayout()
        self.dot = QLabel("✦")
        self.dot.setObjectName("daiDot")
        self.title = QLabel("AI")
        self.title.setObjectName("daiTitle")
        hide = QPushButton("×")
        hide.setObjectName("daiHide")
        hide.setFixedSize(22, 22)
        hide.setCursor(Qt.PointingHandCursor)
        hide.clicked.connect(self.close_requested.emit)
        stop = QPushButton("STOP")
        stop.setObjectName("daiStop")
        stop.setFixedHeight(22)
        stop.setCursor(Qt.PointingHandCursor)
        stop.clicked.connect(self.stop_requested.emit)
        self._stop_btn = stop
        top.addWidget(self.dot)
        top.addWidget(self.title)
        top.addStretch(1)
        top.addWidget(stop)
        top.addWidget(hide)

        self.line = QLabel("Sleeping — say “AI”")
        self.line.setObjectName("daiLine")
        self.line.setWordWrap(True)

        self.hint = QLabel("Google mic. After wakeup, keep speaking the next step.")
        self.hint.setObjectName("daiHint")
        self.hint.setWordWrap(True)

        self.retry = QPushButton("Retry mic")
        self.retry.setObjectName("daiRetry")
        self.retry.setMinimumHeight(26)
        self.retry.clicked.connect(self.retry_requested.emit)
        self.retry.hide()

        self.confirm_host = QWidget()
        cl = QVBoxLayout(self.confirm_host)
        cl.setContentsMargins(0, 2, 0, 0)
        cl.setSpacing(4)
        self.confirm_label = QLabel("Do you mean this?")
        self.confirm_label.setObjectName("daiHint")
        self.confirm_label.setWordWrap(True)
        cl.addWidget(self.confirm_label)
        yn = QHBoxLayout()
        self.yes_btn = QPushButton("YES")
        self.yes_btn.setObjectName("daiChip")
        self.yes_btn.clicked.connect(self.yes_requested.emit)
        self.no_btn = QPushButton("NO")
        self.no_btn.setObjectName("daiChip")
        self.no_btn.clicked.connect(self.no_requested.emit)
        yn.addWidget(self.yes_btn)
        yn.addWidget(self.no_btn)
        cl.addLayout(yn)
        self.chip_box = QVBoxLayout()
        self.chip_box.setSpacing(4)
        cl.addLayout(self.chip_box)
        self.yes_btn.hide()
        self.no_btn.hide()
        self.confirm_host.hide()

        root.addLayout(top)
        root.addWidget(self.line)
        root.addWidget(self.hint)
        root.addWidget(self.retry)
        root.addWidget(self.confirm_host)
        self.set_mode("sleep")

    def set_brand(self, name: str) -> None:
        self._agent_name = (name or "AI").strip() or "AI"
        self.title.setText(self._agent_name)
        if self.line.text().startswith("Sleeping"):
            self.set_mode("sleep")

    def place_corner(self) -> None:
        screen = self.screen()
        if screen is None:
            from PyQt5.QtWidgets import QApplication

            screen = QApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        self.move(geo.right() - self.width() - 18, geo.bottom() - self.height() - 18)

    def set_mode(self, mode: str, detail: str = "") -> None:
        mode = (mode or "sleep").lower()
        if mode != "clarify" and not self._element_confirm:
            self.clear_clarify()
        if mode == "sleep":
            self.dot.setStyleSheet("color:#94a3b8;font-size:14px;")
            self.line.setText(detail or f"Sleeping — say “{self._agent_name}”")
            self.hint.setText("Google mic. Click the pill if wake word is not heard.")
        elif mode == "active":
            self.dot.setStyleSheet("color:#16a34a;font-size:14px;")
            self.line.setText(detail or "Listening — what's next?")
            self.hint.setText(f"Say done or {self._agent_name} sleep to finish. STOP cancels.")
        elif mode == "analyze":
            self.dot.setStyleSheet("color:#818cf8;font-size:14px;")
            self.line.setText(detail or "Analyzing screen…")
        elif mode == "busy":
            self.dot.setStyleSheet("color:#d97706;font-size:14px;")
            self.line.setText(detail or "Working…")
        elif mode == "clarify":
            self.dot.setStyleSheet("color:#818cf8;font-size:14px;")
            self.line.setText(detail or "Do you mean this?")
        elif mode == "error":
            self.dot.setStyleSheet("color:#dc2626;font-size:14px;")
            self.line.setText(detail or "Mic error")
            self.retry.show()
        else:
            self.line.setText(detail or mode)
            self.retry.hide()
        if mode != "error" and hasattr(self, "retry"):
            self.retry.hide()

    def show_clarify(self, heard: str, suggestions: Sequence[str]) -> None:
        self._clarifying = True
        self.setFixedSize(312, 278)
        self.dot.setStyleSheet("color:#818cf8;font-size:14px;")
        self.line.setText(f"Heard: {heard}" if heard else "I only caught part of that")
        self.hint.setText("Do you mean this?")
        self.confirm_label.setText("Do you mean this?")
        self._clear_chips()
        for text in list(suggestions)[:4]:
            btn = QPushButton(text)
            btn.setObjectName("daiChip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda _=False, t=text: self.confirm_requested.emit(t))
            self.chip_box.addWidget(btn)
            self._chip_buttons.append(btn)
        self.confirm_host.show()
        self.place_corner()

    def show_element_confirm(self, prompt: str, suggestions: Sequence[str]) -> None:
        self._clarifying = True
        self._element_confirm = True
        self.setFixedSize(312, 300)
        self.dot.setStyleSheet("color:#818cf8;font-size:14px;")
        self.line.setText(prompt)
        self.hint.setText("Yes clicks it. No waits for a clearer command.")
        self.confirm_label.setText(prompt)
        self.yes_btn.show()
        self.no_btn.show()
        self._clear_chips()
        for text in list(suggestions)[:3]:
            btn = QPushButton(text)
            btn.setObjectName("daiChip")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(28)
            btn.clicked.connect(lambda _=False, t=text: self.confirm_requested.emit(t))
            self.chip_box.addWidget(btn)
            self._chip_buttons.append(btn)
        self.confirm_host.show()
        self.place_corner()

    def clear_clarify(self) -> None:
        if not self._clarifying and not self._chip_buttons:
            if self.height() != 176:
                self.setFixedSize(312, 176)
            self.confirm_host.hide()
            return
        self._clarifying = False
        self._element_confirm = False
        self._clear_chips()
        self.yes_btn.hide()
        self.no_btn.hide()
        self.confirm_host.hide()
        self.setFixedSize(312, 176)

    def _clear_chips(self) -> None:
        for btn in self._chip_buttons:
            self.chip_box.removeWidget(btn)
            btn.deleteLater()
        self._chip_buttons = []

    def hide_for_action(self) -> None:
        self._hidden_for_action = True
        self.hide()

    def show_after_action(self) -> None:
        if self._hidden_for_action:
            self._hidden_for_action = False
            self.show()
            self.raise_()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._drag = event.globalPos() - self.frameGeometry().topLeft()
            self._press_pos = event.globalPos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPos() - self._drag)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        moved = False
        if hasattr(self, "_press_pos") and self._press_pos is not None:
            delta = event.globalPos() - self._press_pos
            moved = abs(delta.x()) > 8 or abs(delta.y()) > 8
        self._drag = None
        self._press_pos = None
        if event.button() == Qt.LeftButton and not moved and not self._clarifying:
            self.tap_requested.emit()
        super().mouseReleaseEvent(event)
