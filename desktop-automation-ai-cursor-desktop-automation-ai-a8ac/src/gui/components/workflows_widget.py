"""List, save, rename, delete, and replay workflows."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QMessageBox,
    QInputDialog,
)


class WorkflowsWidget(QWidget):
    replay_requested = pyqtSignal(int)
    save_from_history_requested = pyqtSignal(str, str)
    refresh_requested = pyqtSignal()
    delete_requested = pyqtSignal(int)
    rename_requested = pyqtSignal(int, str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._items: List[Dict[str, Any]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        title = QLabel("Workflows")
        title.setStyleSheet("font-weight: 700; color: #0f3d4c; font-size: 14px;")
        hint = QLabel("Save multi-step macros and replay them with one click")
        hint.setObjectName("sectionHint")

        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._on_select)

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(140)

        save_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("New workflow name")
        self.btn_save = QPushButton("Save last actions")
        self.btn_save.setObjectName("btnSecondary")
        self.btn_save.clicked.connect(self._on_save)
        save_row.addWidget(self.name_input, stretch=1)
        save_row.addWidget(self.btn_save)

        btn_row = QHBoxLayout()
        self.btn_replay = QPushButton("Replay")
        self.btn_replay.clicked.connect(self._on_replay)
        self.btn_rename = QPushButton("Rename")
        self.btn_rename.setObjectName("btnSecondary")
        self.btn_rename.clicked.connect(self._on_rename)
        self.btn_delete = QPushButton("Delete")
        self.btn_delete.setObjectName("btnDanger")
        self.btn_delete.clicked.connect(self._on_delete)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setObjectName("btnSecondary")
        self.btn_refresh.clicked.connect(self.refresh_requested.emit)
        btn_row.addWidget(self.btn_replay)
        btn_row.addWidget(self.btn_rename)
        btn_row.addWidget(self.btn_delete)
        btn_row.addWidget(self.btn_refresh)

        root.addWidget(title)
        root.addWidget(hint)
        root.addWidget(self.list, stretch=1)
        root.addWidget(self.details)
        root.addLayout(save_row)
        root.addLayout(btn_row)

    def set_workflows(self, workflows: List[Dict[str, Any]]) -> None:
        self._items = workflows
        self.list.clear()
        for wf in workflows:
            item = QListWidgetItem(f"{wf['name']}  ({len(wf.get('tasks', []))} steps)")
            item.setData(256, wf["workflow_id"])  # Qt.UserRole
            self.list.addItem(item)
        self.details.clear()

    def _selected_id(self) -> Optional[int]:
        item = self.list.currentItem()
        if not item:
            return None
        return int(item.data(256))

    def _on_select(self, current: Optional[QListWidgetItem], _prev) -> None:
        if not current:
            self.details.clear()
            return
        wid = int(current.data(256))
        wf = next((w for w in self._items if w["workflow_id"] == wid), None)
        if not wf:
            return
        lines = [f"Name: {wf['name']}", f"Description: {wf.get('description') or '-'}", "", "Steps:"]
        for task in wf.get("tasks", []):
            lines.append(
                f"  {task['step_order']}. {task['intent']}"
                f" app={task.get('target_app') or '-'} "
                f"element={task.get('target_element') or '-'} "
                f"value={task.get('input_value') or '-'}"
            )
        self.details.setPlainText("\n".join(lines))

    def _on_replay(self) -> None:
        wid = self._selected_id()
        if wid is None:
            QMessageBox.information(self, "Workflows", "Select a workflow first.")
            return
        self.replay_requested.emit(wid)

    def _on_delete(self) -> None:
        wid = self._selected_id()
        if wid is None:
            return
        if QMessageBox.question(self, "Delete", "Delete this workflow?") != QMessageBox.Yes:
            return
        self.delete_requested.emit(wid)

    def _on_rename(self) -> None:
        wid = self._selected_id()
        if wid is None:
            return
        name, ok = QInputDialog.getText(self, "Rename workflow", "New name:")
        if ok and name.strip():
            self.rename_requested.emit(wid, name.strip())

    def _on_save(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.information(self, "Workflows", "Enter a name for the new workflow.")
            return
        self.save_from_history_requested.emit(name, "")
        self.name_input.clear()
