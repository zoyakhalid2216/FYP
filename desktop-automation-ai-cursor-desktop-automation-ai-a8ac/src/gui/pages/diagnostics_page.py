"""System diagnostics with per-component Test buttons."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class DiagnosticsPage(QWidget):
    refresh_requested = pyqtSignal()
    test_capture_requested = pyqtSignal()
    test_ocr_requested = pyqtSignal()
    test_mouse_requested = pyqtSignal()
    test_keyboard_requested = pyqtSignal()
    test_mic_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(12)

        t = QLabel("System Diagnostics")
        t.setObjectName("pageTitle")
        s = QLabel("Check every FYP component before a demo. Use Test to exercise live hardware.")
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        root.addWidget(t)
        root.addWidget(s)

        row = QHBoxLayout()
        refresh = QPushButton("Re-scan")
        refresh.setObjectName("btnPrimary")
        refresh.clicked.connect(self.refresh_requested.emit)
        row.addWidget(refresh)
        row.addStretch(1)
        root.addLayout(row)

        self.rows_host = QVBoxLayout()
        self.rows_host.setSpacing(8)
        root.addLayout(self.rows_host)

        tests = QFrame()
        tests.setObjectName("panelCard")
        tl = QVBoxLayout(tests)
        tl.setContentsMargins(16, 14, 16, 14)
        head = QLabel("Live tests")
        head.setObjectName("sectionTitle")
        tl.addWidget(head)
        buttons = QHBoxLayout()
        for label, sig in (
            ("Screen capture", self.test_capture_requested),
            ("OCR", self.test_ocr_requested),
            ("Mouse", self.test_mouse_requested),
            ("Keyboard", self.test_keyboard_requested),
            ("Microphone", self.test_mic_requested),
        ):
            b = QPushButton(f"Test {label}")
            b.setObjectName("btnSecondary")
            b.clicked.connect(sig.emit)
            buttons.addWidget(b)
        tl.addLayout(buttons)
        self.test_out = QLabel("Results appear here.")
        self.test_out.setObjectName("pageSubtitle")
        self.test_out.setWordWrap(True)
        tl.addWidget(self.test_out)
        root.addWidget(tests)
        root.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll)
        self._cards: List[QFrame] = []

    def set_results(self, rows: List[Dict[str, Any]]) -> None:
        while self.rows_host.count():
            item = self.rows_host.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for row in rows:
            card = QFrame()
            card.setObjectName("panelCard")
            hl = QHBoxLayout(card)
            hl.setContentsMargins(14, 10, 14, 10)
            ok = bool(row.get("ok"))
            mark = QLabel("✓ Ready" if ok else "✕ Issue")
            mark.setStyleSheet(
                "color:#047857;font-weight:700;" if ok else "color:#b91c1c;font-weight:700;"
            )
            name = QLabel(str(row.get("name") or ""))
            name.setObjectName("sectionTitle")
            detail = QLabel(str(row.get("detail") or ""))
            detail.setObjectName("pageSubtitle")
            detail.setWordWrap(True)
            hl.addWidget(name, 2)
            hl.addWidget(detail, 4)
            hl.addWidget(mark, 1)
            self.rows_host.addWidget(card)

    def set_test_output(self, text: str) -> None:
        self.test_out.setText(text)
