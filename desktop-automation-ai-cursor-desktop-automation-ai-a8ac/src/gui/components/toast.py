"""Transient toast notifications in the main window."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLabel, QWidget


class ToastHost:
    def __init__(self, parent: QWidget) -> None:
        self.parent = parent
        self._label = QLabel(parent)
        self._label.setObjectName("toastLabel")
        self._label.hide()
        self._timer = QTimer(parent)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._label.hide)

    def show(self, message: str, kind: str = "info", ms: int = 3200) -> None:
        colors = {
            "success": ("#ecfdf5", "#047857", "#a7f3d0"),
            "error": ("#fef2f2", "#b91c1c", "#fecaca"),
            "warning": ("#fffbeb", "#b45309", "#fde68a"),
            "safety": ("#fef2f2", "#991b1b", "#fecaca"),
            "info": ("#eef2ff", "#4338ca", "#c7d2fe"),
        }
        bg, fg, bd = colors.get(kind, colors["info"])
        self._label.setText(message)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"background:{bg};color:{fg};border:1px solid {bd};"
            "border-radius:10px;padding:10px 14px;font-weight:600;"
        )
        self._label.adjustSize()
        self._label.setFixedWidth(min(360, max(220, self.parent.width() // 3)))
        self._label.adjustSize()
        x = self.parent.width() - self._label.width() - 24
        y = 56
        self._label.move(max(16, x), y)
        self._label.show()
        self._label.raise_()
        self._timer.start(ms)
