"""Workflow Management — stats, card grid, live logs."""

from __future__ import annotations

from typing import Any, Dict, List

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class WorkflowsPage(QWidget):
    run_requested = pyqtSignal(int)
    create_requested = pyqtSignal(str, str)
    delete_requested = pyqtSignal(int)
    edit_requested = pyqtSignal(int)
    refresh_requested = pyqtSignal()
    record_start_requested = pyqtSignal()
    record_stop_save_requested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._workflows: List[Dict[str, Any]] = []
        self._recording = False

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

        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        t = QLabel("Workflow Management")
        t.setObjectName("pageTitle")
        s = QLabel(
            "Record live steps (voice or typed), save them as a workflow, "
            "then say “Run <workflow name>” anytime."
        )
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        titles.addWidget(t)
        titles.addWidget(s)
        head.addLayout(titles, 1)

        self.btn_record = QPushButton("● Record steps")
        self.btn_record.setObjectName("btnSecondary")
        self.btn_record.setMinimumHeight(36)
        self.btn_record.clicked.connect(self._toggle_record)

        create = QPushButton("+ Save as workflow")
        create.setObjectName("btnPrimary")
        create.setMinimumHeight(36)
        create.setToolTip("Saves recorded steps (or last command actions) as a named workflow")
        create.clicked.connect(self._create)
        head.addWidget(self.btn_record, 0, Qt.AlignTop)
        head.addWidget(create, 0, Qt.AlignTop)
        root.addLayout(head)

        self.record_status = QLabel(
            "Tip: click Record steps → do your actions by voice/type → Save as workflow."
        )
        self.record_status.setObjectName("pageSubtitle")
        self.record_status.setWordWrap(True)
        root.addWidget(self.record_status)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.s_total = self._stat("Total Workflows", "0")
        self.s_voice = self._stat("Voice Shortcuts", "0")
        self.s_steps = self._stat("Average Steps", "0")
        self.s_today = self._stat("Executions Today", "0")
        for w in (self.s_total, self.s_voice, self.s_steps, self.s_today):
            stats.addWidget(w, 1)
        root.addLayout(stats)

        grid_host = QWidget()
        self.grid = QGridLayout(grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)
        self.grid.setAlignment(Qt.AlignTop)
        root.addWidget(grid_host)

        logs_card = QFrame()
        logs_card.setObjectName("panelCard")
        ll = QVBoxLayout(logs_card)
        ll.setContentsMargins(16, 14, 16, 14)
        ll.setSpacing(8)
        lh = QHBoxLayout()
        lh.addWidget(self._section("Live Execution Logs"))
        lh.addStretch()
        refresh = QPushButton("Refresh")
        refresh.setObjectName("btnGhost")
        refresh.clicked.connect(self.refresh_requested.emit)
        lh.addWidget(refresh)
        ll.addLayout(lh)
        self.live_logs = QLabel("No recent workflow runs yet.")
        self.live_logs.setObjectName("pageSubtitle")
        self.live_logs.setWordWrap(True)
        ll.addWidget(self.live_logs)
        root.addWidget(logs_card)

        foot = QLabel("© 2026 Automate AI · Local desktop automation")
        foot.setObjectName("footerLabel")
        root.addWidget(foot)
        root.addStretch(1)

        scroll.setWidget(host)
        outer.addWidget(scroll)

    def _section(self, text: str) -> QLabel:
        lab = QLabel(text)
        lab.setObjectName("sectionTitle")
        return lab

    def _stat(self, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("metricCard")
        card.setMinimumHeight(88)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        l = QLabel(label)
        l.setObjectName("metricLabel")
        l.setWordWrap(True)
        v = QLabel(value)
        v.setObjectName("metricValue")
        v.setMinimumHeight(30)
        lay.addWidget(l)
        lay.addWidget(v)
        card.value_label = v  # type: ignore[attr-defined]
        return card

    def set_workflows(
        self,
        workflows: List[Dict[str, Any]],
        *,
        today_executions: int = 0,
        avg_steps: float = 0.0,
    ) -> None:
        self._workflows = workflows
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        voice_count = sum(
            1 for w in workflows if str(w.get("trigger_type", "")).lower() == "voice"
        )
        self.s_total.value_label.setText(str(len(workflows)))  # type: ignore[attr-defined]
        self.s_voice.value_label.setText(str(voice_count))  # type: ignore[attr-defined]
        self.s_steps.value_label.setText(f"{avg_steps:.1f}")  # type: ignore[attr-defined]
        self.s_today.value_label.setText(str(today_executions))  # type: ignore[attr-defined]

        # Two columns — avoids cramped 3-col overlap on typical laptop widths
        cols = 2
        for idx, wf in enumerate(workflows):
            card = self._workflow_card(wf)
            self.grid.addWidget(card, idx // cols, idx % cols)

        add = QFrame()
        add.setObjectName("workflowCard")
        add.setMinimumHeight(150)
        add.setStyleSheet(
            "#workflowCard{border:1px dashed #cbd5e1;background:#fafbfc;}"
        )
        al = QVBoxLayout(add)
        al.setContentsMargins(16, 18, 16, 18)
        al.setSpacing(8)
        plus = QLabel("+")
        plus.setAlignment(Qt.AlignCenter)
        plus.setStyleSheet("font-size:26px;font-weight:700;color:#94a3b8;")
        desc = QLabel("Design a custom automation chain for your desktop apps.")
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignCenter)
        desc.setObjectName("pageSubtitle")
        btn = QPushButton("Add New Module")
        btn.setObjectName("btnSecondary")
        btn.setMinimumHeight(34)
        btn.clicked.connect(self._create)
        al.addStretch(1)
        al.addWidget(plus)
        al.addWidget(desc)
        al.addWidget(btn, 0, Qt.AlignCenter)
        al.addStretch(1)
        self.grid.addWidget(add, len(workflows) // cols, len(workflows) % cols)

        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    def _workflow_card(self, wf: Dict[str, Any]) -> QFrame:
        card = QFrame()
        card.setObjectName("workflowCard")
        card.setMinimumHeight(150)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        title = QLabel(wf.get("name", "Workflow"))
        title.setObjectName("sectionTitle")
        title.setWordWrap(True)

        tasks = wf.get("tasks") or []
        meta = QLabel(
            f"Created {str(wf.get('created_at', ''))[:10] or '—'}  ·  "
            f"{len(tasks)} steps  ·  "
            f"{wf.get('trigger_type', 'manual')}"
        )
        meta.setObjectName("pageSubtitle")
        meta.setWordWrap(True)
        chain_bits = []
        for i, t in enumerate(tasks[:4], start=1):
            chain_bits.append(f"{i}. {t.get('intent', 'step')}")
        if len(tasks) > 4:
            chain_bits.append("…")
        chain = QLabel(" → ".join(chain_bits) if chain_bits else "No steps yet — Edit to add a visual chain.")
        chain.setObjectName("pageSubtitle")
        chain.setWordWrap(True)

        row = QHBoxLayout()
        row.setSpacing(8)
        run = QPushButton("Run")
        run.setObjectName("btnPrimary")
        run.setMinimumHeight(32)
        run.clicked.connect(
            lambda _=False, i=wf["workflow_id"]: self.run_requested.emit(i)
        )
        edit = QPushButton("Edit")
        edit.setObjectName("btnSecondary")
        edit.setMinimumHeight(32)
        edit.clicked.connect(
            lambda _=False, i=wf["workflow_id"]: self.edit_requested.emit(i)
        )
        delete = QPushButton("Delete")
        delete.setObjectName("btnGhost")
        delete.setMinimumHeight(32)
        delete.clicked.connect(
            lambda _=False, i=wf["workflow_id"]: self.delete_requested.emit(i)
        )
        row.addWidget(run)
        row.addWidget(edit)
        row.addWidget(delete)
        row.addStretch(1)

        lay.addWidget(title)
        lay.addWidget(meta)
        lay.addWidget(chain)
        lay.addStretch(1)
        lay.addLayout(row)
        return card

    def _create(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Workflow", "Workflow name:")
        if not ok or not name.strip():
            return
        desc, ok2 = QInputDialog.getText(
            self, "Save Workflow", "Description (optional):"
        )
        if not ok2:
            desc = ""
        self.create_requested.emit(name.strip(), (desc or "").strip())

    def _toggle_record(self) -> None:
        if self._recording:
            self.set_recording(False)
            self.record_stop_save_requested.emit()
        else:
            self.record_start_requested.emit()

    def set_recording(self, active: bool, step_count: int = 0) -> None:
        self._recording = active
        if active:
            self.btn_record.setText("■ Stop recording")
            self.btn_record.setObjectName("btnDanger")
            self.record_status.setText(
                f"Recording… ({step_count} actions). Use Voice or type commands, then Save as workflow."
            )
        else:
            self.btn_record.setText("● Record steps")
            self.btn_record.setObjectName("btnSecondary")
            if step_count:
                self.record_status.setText(
                    f"Recorded {step_count} actions. Click Save as workflow and give it a name."
                )
            else:
                self.record_status.setText(
                    "Tip: click Record steps → do your actions by voice/type → Save as workflow."
                )
        self.btn_record.style().unpolish(self.btn_record)
        self.btn_record.style().polish(self.btn_record)

    def set_live_logs(self, lines: List[str]) -> None:
        if not lines:
            self.live_logs.setText("No recent workflow runs yet.")
        else:
            self.live_logs.setText("\n".join(lines[:6]))
