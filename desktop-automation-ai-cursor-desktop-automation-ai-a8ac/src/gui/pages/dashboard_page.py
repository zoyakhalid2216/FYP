"""System Dashboard — clean metrics, trend, activity, voice CTA."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.components.chart_widget import BarRatioWidget, LineChartWidget


class DashboardPage(QWidget):
    open_voice = pyqtSignal()
    open_agent = pyqtSignal()
    open_history = pyqtSignal()
    open_workflows = pyqtSignal()
    run_diagnostics = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        host = QWidget()
        root = QVBoxLayout(host)
        root.setContentsMargins(28, 22, 28, 20)
        root.setSpacing(16)

        title = QLabel("System Dashboard")
        title.setObjectName("pageTitle")
        sub = QLabel("Monitor automations, success rate, and recent activity.")
        sub.setObjectName("pageSubtitle")
        sub.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(sub)

        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.m_total = self._metric("Total executions", "0", "From your history")
        self.m_rate = self._metric("Success Rate", "—", "Across all executions")
        self.m_failed = self._metric("Failed", "0", "Needs review")
        self.m_today = self._metric("Executions Today", "0", "Local SQLite logs")
        self.m_avg = self._metric("Avg time", "—", "Milliseconds")
        for w in (self.m_total, self.m_rate, self.m_failed, self.m_today, self.m_avg):
            metrics.addWidget(w, 1)
        root.addLayout(metrics)

        mid = QHBoxLayout()
        mid.setSpacing(12)

        trend = QFrame()
        trend.setObjectName("panelCard")
        tl = QVBoxLayout(trend)
        tl.setContentsMargins(18, 16, 18, 16)
        tl.setSpacing(8)
        tl.addWidget(self._section("Automation Trend"))
        ts = QLabel("Executions per day (last 7 days).")
        ts.setObjectName("pageSubtitle")
        tl.addWidget(ts)
        self.trend_chart = LineChartWidget()
        tl.addWidget(self.trend_chart, 1)
        self.ratio = BarRatioWidget()
        tl.addWidget(self.ratio)

        side = QVBoxLayout()
        side.setSpacing(12)

        actions = QFrame()
        actions.setObjectName("panelCard")
        al = QVBoxLayout(actions)
        al.setContentsMargins(16, 14, 16, 14)
        al.setSpacing(8)
        al.addWidget(self._section("Quick Actions"))
        b1 = QPushButton("New Automation Workflow")
        b1.setObjectName("btnPrimary")
        b1.setMinimumHeight(36)
        b1.clicked.connect(self.open_workflows.emit)
        b2 = QPushButton("Open Diagnostics")
        b2.setObjectName("btnSecondary")
        b2.setMinimumHeight(34)
        b2.clicked.connect(self.run_diagnostics.emit)
        b3 = QPushButton("Launch Voice Assistant")
        b3.setObjectName("btnSecondary")
        b3.setMinimumHeight(34)
        b3.clicked.connect(self.open_voice.emit)
        al.addWidget(b1)
        al.addWidget(b2)
        al.addWidget(b3)

        resources = QFrame()
        resources.setObjectName("panelCard")
        rl = QVBoxLayout(resources)
        rl.setContentsMargins(16, 14, 16, 14)
        rl.setSpacing(6)
        rl.addWidget(self._section("System Resources"))
        self.res_cpu = QLabel("Mode: Live automation")
        self.res_ram = QLabel("Vision: OpenCV + Tesseract")
        self.res_api = QLabel("API Connection: Local")
        self.res_lat = QLabel("Engine: spaCy / NLTK + PyAutoGUI")
        for lab in (self.res_cpu, self.res_ram, self.res_api, self.res_lat):
            lab.setObjectName("pageSubtitle")
            lab.setWordWrap(True)
            rl.addWidget(lab)

        side.addWidget(actions)
        side.addWidget(resources)
        side.addStretch()

        mid.addWidget(trend, 7)
        mid.addLayout(side, 3)
        root.addLayout(mid)

        bottom = QHBoxLayout()
        bottom.setSpacing(12)

        table_wrap = QFrame()
        table_wrap.setObjectName("panelCard")
        twl = QVBoxLayout(table_wrap)
        twl.setContentsMargins(16, 14, 16, 14)
        twl.setSpacing(10)
        thr = QHBoxLayout()
        thr.addWidget(self._section("Recent Automation Activity"))
        thr.addStretch()
        view_all = QPushButton("View All History")
        view_all.setObjectName("btnGhost")
        view_all.clicked.connect(self.open_history.emit)
        thr.addWidget(view_all)
        twl.addLayout(thr)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Task ID", "Automation Name", "Category", "Execution Time", "Status"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(90)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setMinimumHeight(200)
        twl.addWidget(self.table)

        voice = QFrame()
        voice.setObjectName("panelCard")
        voice.setMinimumWidth(200)
        voice.setMaximumWidth(260)
        vl = QVBoxLayout(voice)
        vl.setContentsMargins(16, 14, 16, 14)
        vl.setSpacing(10)
        vl.addWidget(self._section("Try Voice Commands"))
        tip = QLabel(
            "Control your desktop with natural language. Try saying “Open notepad”."
        )
        tip.setWordWrap(True)
        tip.setObjectName("pageSubtitle")
        vl.addWidget(tip)
        vl.addStretch(1)
        launch = QPushButton("Launch AI Agent")
        launch.setObjectName("btnPrimary")
        launch.setMinimumHeight(38)
        launch.clicked.connect(self.open_agent.emit)
        vl.addWidget(launch)

        bottom.addWidget(table_wrap, 7)
        bottom.addWidget(voice, 3)
        root.addLayout(bottom)

        foot = QLabel("© 2026 Automate AI · Your desktop. Your commands. Automated.")
        foot.setObjectName("footerLabel")
        root.addWidget(foot)

        scroll.setWidget(host)
        outer.addWidget(scroll)

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("sectionTitle")
        return lab

    def _metric(self, label: str, value: str, hint: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        card.setMinimumHeight(108)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)

        l = QLabel(label)
        l.setObjectName("metricLabel")
        l.setWordWrap(True)

        v = QLabel(value)
        v.setObjectName("metricValue")
        v.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        v.setMinimumHeight(34)

        h = QLabel(hint)
        h.setObjectName("metricHint")
        h.setWordWrap(True)

        lay.addWidget(l)
        lay.addWidget(v)
        lay.addStretch(1)
        lay.addWidget(h)
        card.value_label = v  # type: ignore[attr-defined]
        card.hint_label = h  # type: ignore[attr-defined]
        return card

    def update_stats(self, stats: Dict[str, Any], dry_run: bool = True) -> None:
        total = int(stats.get("total", 0) or 0)
        success = int(stats.get("success", 0) or 0)
        failed = int(stats.get("failed", 0) or 0)
        self.m_total.value_label.setText(str(total))  # type: ignore[attr-defined]
        rate = stats.get("success_rate", 100)
        self.m_rate.value_label.setText(f"{rate}%" if total else "—")  # type: ignore[attr-defined]
        self.m_failed.value_label.setText(str(failed))  # type: ignore[attr-defined]
        self.m_today.value_label.setText(str(stats.get("today", 0)))  # type: ignore[attr-defined]
        avg = int(stats.get("avg_ms") or 0)
        self.m_avg.value_label.setText(f"{avg} ms" if total else "—")  # type: ignore[attr-defined]
        self.res_cpu.setText(f"Mode: {'Dry-run safe' if dry_run else 'LIVE automation'}")
        self.ratio.set_counts(success, failed)
        from datetime import date, timedelta

        daily = stats.get("daily") or {}
        points = []
        today = date.today()
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            key = d.isoformat()
            points.append((d.strftime("%a"), float(daily.get(key, 0))))
        self.trend_chart.set_series(points)

    def update_activity(self, rows: List[Dict[str, Any]]) -> None:
        self.table.setRowCount(0)
        for item in rows[:8]:
            r = self.table.rowCount()
            self.table.insertRow(r)
            log_id = str(item.get("log_id", ""))
            details = item.get("details_json") or {}
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except Exception:
                    details = {}
            name = (
                (details.get("parsed") or {}).get("intent")
                or item.get("action_id")
                or "Command"
            )
            vals = [
                f"TX-{log_id}",
                str(name),
                "Automation",
                str(item.get("started_at", ""))[-8:],
                str(item.get("status", "")),
            ]
            for c, val in enumerate(vals):
                cell = QTableWidgetItem(val)
                cell.setToolTip(val)
                self.table.setItem(r, c, cell)
        count = len(rows)
        _ = count
