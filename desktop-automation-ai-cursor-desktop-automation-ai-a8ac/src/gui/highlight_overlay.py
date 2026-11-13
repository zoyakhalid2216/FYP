"""Temporary glowing outline over a detected UI element."""

from __future__ import annotations

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QWidget


class HighlightOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def show_box(self, x: int, y: int, w: int, h: int, *, ms: int = 700) -> None:
        pad = 6
        self.setGeometry(max(0, x - pad), max(0, y - pad), max(24, w + pad * 2), max(24, h + pad * 2))
        self.show()
        self.raise_()
        self._timer.start(max(200, ms))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(99, 102, 241, 230))
        pen.setWidth(3)
        painter.setPen(pen)
        painter.setBrush(QColor(99, 102, 241, 40))
        painter.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 8, 8)
