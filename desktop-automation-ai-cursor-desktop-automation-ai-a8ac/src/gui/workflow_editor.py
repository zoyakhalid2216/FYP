"""Visual workflow step editor: edit, duplicate, delete, move."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt5.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

INTENTS = [
    "open_app",
    "open_file",
    "wait",
    "search_web",
    "click_text",
    "click_button",
    "type_text",
    "fill_form",
    "press_key",
    "scroll",
    "copy_file",
    "move_file",
]


class WorkflowEditorDialog(QDialog):
    def __init__(self, workflow: Dict[str, Any], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Edit — {workflow.get('name') or 'Workflow'}")
        self.resize(640, 520)
        self._rows: List[Dict[str, Any]] = []
        root = QVBoxLayout(self)
        self.name = QLineEdit(workflow.get("name") or "")
        root.addWidget(QLabel("Workflow name"))
        root.addWidget(self.name)
        hint = QLabel("Each card is one step. Use ↑ ↓ to reorder.")
        hint.setObjectName("pageSubtitle")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.host = QWidget()
        self.list_layout = QVBoxLayout(self.host)
        self.list_layout.setSpacing(8)
        scroll.setWidget(self.host)
        root.addWidget(scroll, 1)

        add = QPushButton("+ Add step")
        add.setObjectName("btnSecondary")
        add.clicked.connect(lambda: self._add_task({"intent": "wait", "input_value": "1"}))
        root.addWidget(add)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        for task in workflow.get("tasks") or []:
            self._add_task(task)

    def _add_task(self, task: Dict[str, Any], index: Optional[int] = None) -> None:
        card = QWidget()
        card.setObjectName("panelCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 8, 10, 8)
        intent = QComboBox()
        intent.addItems(INTENTS)
        intent.setCurrentText(str(task.get("intent") or "wait"))
        target = QLineEdit(str(task.get("target_app") or task.get("target_element") or ""))
        target.setPlaceholderText("app / element / source")
        value = QLineEdit(str(task.get("input_value") or ""))
        value.setPlaceholderText("text / seconds / destination")
        up = QPushButton("↑")
        down = QPushButton("↓")
        dup = QPushButton("Duplicate")
        delete = QPushButton("Delete")
        for b in (up, down, dup, delete):
            b.setObjectName("btnGhost")
        row.addWidget(intent, 2)
        row.addWidget(target, 3)
        row.addWidget(value, 3)
        row.addWidget(up)
        row.addWidget(down)
        row.addWidget(dup)
        row.addWidget(delete)
        meta = {"widget": card, "intent": intent, "target": target, "value": value}
        if index is None:
            self._rows.append(meta)
            self.list_layout.addWidget(card)
        else:
            self._rows.insert(index, meta)
            self.list_layout.insertWidget(index, card)

        up.clicked.connect(lambda _=False, c=card: self._move(c, -1))
        down.clicked.connect(lambda _=False, c=card: self._move(c, 1))
        dup.clicked.connect(lambda _=False, m=meta: self._duplicate(m))
        delete.clicked.connect(lambda _=False, c=card: self._delete(c))

    def _index_of(self, card: QWidget) -> int:
        for i, row in enumerate(self._rows):
            if row["widget"] is card:
                return i
        return -1

    def _move(self, card: QWidget, delta: int) -> None:
        i = self._index_of(card)
        j = i + delta
        if i < 0 or j < 0 or j >= len(self._rows):
            return
        self._rows[i], self._rows[j] = self._rows[j], self._rows[i]
        self.list_layout.removeWidget(card)
        self.list_layout.insertWidget(j, card)

    def _duplicate(self, meta: Dict[str, Any]) -> None:
        i = self._index_of(meta["widget"])
        task = {
            "intent": meta["intent"].currentText(),
            "target_app": meta["target"].text(),
            "target_element": meta["target"].text(),
            "input_value": meta["value"].text(),
        }
        self._add_task(task, index=i + 1)

    def _delete(self, card: QWidget) -> None:
        i = self._index_of(card)
        if i < 0:
            return
        self._rows.pop(i)
        self.list_layout.removeWidget(card)
        card.deleteLater()

    def result_payload(self) -> Dict[str, Any]:
        tasks = []
        for i, row in enumerate(self._rows, start=1):
            intent = row["intent"].currentText()
            target = row["target"].text().strip()
            value = row["value"].text().strip()
            params: Dict[str, Any] = {}
            if intent == "wait":
                try:
                    params["seconds"] = float(value or 1)
                except ValueError:
                    params["seconds"] = 1.0
            elif intent == "search_web":
                params["query"] = value
            elif intent == "scroll":
                params["direction"] = value or "down"
                params["amount"] = 3
            elif intent == "fill_form":
                params["field"] = target
                params["text"] = value
            elif intent in ("copy_file", "move_file"):
                params["source"] = target
                params["destination"] = value
            tasks.append(
                {
                    "intent": intent,
                    "target_app": target if intent in ("open_app", "open_file") else "",
                    "target_element": target if intent.startswith("click") or intent == "fill_form" else "",
                    "input_value": value,
                    "params": params,
                    "step_order": i,
                }
            )
        return {"name": self.name.text().strip(), "tasks": tasks}
