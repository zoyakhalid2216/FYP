"""Execution History screen with Screen_capture details."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QFrame,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)


class HistoryPage(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(14)

        title = QLabel("Execution History")
        title.setObjectName("pageTitle")
        sub = QLabel(
            "Review run details, durations, errors, and diagnostic Screen_capture clips."
        )
        sub.setObjectName("pageSubtitle")
        root.addWidget(title)
        root.addWidget(sub)

        card = QFrame()
        card.setObjectName("panelCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 14, 16, 14)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Log ID", "Status", "Duration (ms)", "Action", "Started", "Error"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setMinimumSectionSize(80)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        cl.addWidget(self.table)
        root.addWidget(card, 1)

        self.detail = QLabel("Select a row to inspect the AI plan, actions, and captures.")
        self.detail.setObjectName("pageSubtitle")
        self.detail.setWordWrap(True)
        root.addWidget(self.detail)
        self.plan_view = QLabel("")
        self.plan_view.setObjectName("pageSubtitle")
        self.plan_view.setWordWrap(True)
        root.addWidget(self.plan_view)
        self.table.itemSelectionChanged.connect(self._on_select)
        self._rows: List[Dict[str, Any]] = []
        self._captures_by_log: Dict[int, List[Dict[str, Any]]] = {}

    def update_logs(
        self,
        rows: List[Dict[str, Any]],
        captures_by_log: Optional[Dict[int, List[Dict[str, Any]]]] = None,
    ) -> None:
        self._rows = rows
        self._captures_by_log = captures_by_log or {}
        self.table.setRowCount(0)
        for item in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            vals = [
                str(item.get("log_id", "")),
                str(item.get("status", "")),
                str(item.get("duration_ms", 0)),
                str(item.get("action_id", "")),
                str(item.get("started_at", "")),
                str(item.get("error_message", "") or "—"),
            ]
            for c, val in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(val))

    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx < 0 or idx >= len(self._rows):
            return
        item = self._rows[idx]
        details = item.get("details_json") or {}
        if isinstance(details, str):
            try:
                details = json.loads(details)
            except Exception:
                details = {}
        log_id = int(item.get("log_id") or 0)
        captures = self._captures_by_log.get(log_id) or []
        capture_lines = []
        for cap in captures[:5]:
            capture_lines.append(
                f"• {cap.get('file_path')} "
                f"({cap.get('width')}×{cap.get('height')}) "
                f"element={cap.get('element_found') or '—'}"
            )
        capture_txt = "\n".join(capture_lines) if capture_lines else "No screenshots for this log."
        plan = details.get("plan") if isinstance(details, dict) else {}
        steps = []
        if isinstance(plan, dict):
            for st in plan.get("steps") or []:
                mark = {"done": "✓", "failed": "✕"}.get(st.get("status"), "○")
                steps.append(f"{mark} {st.get('title')}")
        parsed = details.get("parsed") if isinstance(details, dict) else {}
        conf = ""
        if isinstance(parsed, dict) and parsed.get("confidence") is not None:
            conf = f"{int(float(parsed.get('confidence') or 0) * 100)}%"
        self.detail.setText(
            f"Execution #{item.get('log_id')}   ·   {item.get('status')}\n"
            f"Duration: {item.get('duration_ms')} ms   ·   AI confidence: {conf or '—'}\n"
            f"Completed: {details.get('completed', '—')}   Remaining: {details.get('remaining', '—')}\n"
            f"Error: {item.get('error_message') or '—'}"
        )
        self.plan_view.setText(
            ("Actions:\n" + "\n".join(steps[:12]) + "\n\n" if steps else "")
            + f"Captures:\n{capture_txt}"
        )
