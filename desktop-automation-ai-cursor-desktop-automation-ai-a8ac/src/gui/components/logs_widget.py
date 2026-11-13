"""Timestamped execution log console."""

from __future__ import annotations

from datetime import datetime

from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit, QFrame


class LogsWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        title = QLabel("Activity log")
        title.setStyleSheet("font-weight: 700; color: #0f3d4c; font-size: 14px;")

        frame = QFrame()
        frame.setObjectName("logFrame")
        frame_layout = QVBoxLayout(frame)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2000)
        self.console.setStyleSheet(
            "QPlainTextEdit { background: #102227; color: #d7e6ea; border: none; "
            "font-family: 'IBM Plex Mono', 'Cascadia Mono', Consolas, monospace; }"
        )
        frame_layout.addWidget(self.console)

        layout.addWidget(title)
        layout.addWidget(frame, stretch=1)

    def append(self, message: str, level: str = "info") -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "info": "#d7e6ea",
            "success": "#7ddea0",
            "error": "#ff8f8a",
            "warn": "#f0c674",
        }
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors.get(level, "#d7e6ea")))
        cursor = self.console.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(f"[{stamp}] {message}\n", fmt)
        self.console.setTextCursor(cursor)
        self.console.ensureCursorVisible()
