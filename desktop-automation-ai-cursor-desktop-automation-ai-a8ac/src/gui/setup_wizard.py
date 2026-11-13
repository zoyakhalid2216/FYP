"""First-run setup wizard so FYP demos fail less often."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.diagnostics import probe_all


class SetupWizard(QDialog):
    def __init__(self, config: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Welcome to Automate AI")
        self.setMinimumWidth(480)
        root = QVBoxLayout(self)
        title = QLabel("Let’s set things up")
        title.setObjectName("pageTitle")
        body = QLabel("Your desktop. Your commands. Automated.\nChecking microphone, capture, OCR, and automation.")
        body.setObjectName("pageSubtitle")
        body.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(body)
        self.lines: List[QLabel] = []
        self._host = QVBoxLayout()
        root.addLayout(self._host)
        self.finish = QPushButton("Finish setup")
        self.finish.setObjectName("btnPrimary")
        self.finish.clicked.connect(self.accept)
        root.addWidget(self.finish)
        self._fill(probe_all(config))

    def _fill(self, rows: List[Dict[str, Any]]) -> None:
        while self._host.count():
            item = self._host.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        for i, row in enumerate(rows, start=1):
            ok = "✓" if row.get("ok") else "○"
            lab = QLabel(f"{i}  {ok}  {row.get('name')} — {row.get('detail')}")
            lab.setWordWrap(True)
            self._host.addWidget(lab)
