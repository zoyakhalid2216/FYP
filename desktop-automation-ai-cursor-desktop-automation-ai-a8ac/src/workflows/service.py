"""Save, list, edit, and prepare multi-step workflows."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from src.db.database import Database
from src.db.repositories import (
    AutomationRuleRepository,
    TaskRepository,
    WorkflowRepository,
)
from src.vision.search_result import FIRST_RESULT_ELEMENT, first_result_entities


class WorkflowService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.workflows = WorkflowRepository(db)
        self.tasks = TaskRepository(db)
        self.rules = AutomationRuleRepository(db)

    def list_workflows(self, user_id: int) -> List[Dict[str, Any]]:
        items = self.workflows.list_for_user(user_id)
        for item in items:
            item["tasks"] = self.tasks.list_for_workflow(item["workflow_id"])
            item["rules"] = self.rules.list_for_workflow(item["workflow_id"])
        return items

    def get_workflow(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        wf = self.workflows.get(workflow_id)
        if not wf:
            return None
        wf["tasks"] = self.tasks.list_for_workflow(workflow_id)
        wf["rules"] = self.rules.list_for_workflow(workflow_id)
        return wf

    def create_workflow(
        self,
        user_id: int,
        name: str,
        description: str = "",
        tasks: Optional[List[Dict[str, Any]]] = None,
        trigger_type: str = "manual",
    ) -> int:
        wid = self.workflows.create(user_id, name, description, trigger_type=trigger_type)
        self.rules.add(wid, "Always run", condition='{"when":"manual"}', action="run_workflow", priority=10)
        if tasks:
            self.tasks.replace_tasks(wid, tasks)
        return wid

    def rename_workflow(self, workflow_id: int, name: str) -> None:
        self.workflows.rename(workflow_id, name)

    def delete_workflow(self, workflow_id: int) -> None:
        self.workflows.delete(workflow_id)

    def save_tasks(self, workflow_id: int, tasks: List[Dict[str, Any]]) -> None:
        self.tasks.replace_tasks(workflow_id, tasks)

    def find_by_name(self, user_id: int, name: str) -> Optional[Dict[str, Any]]:
        """Exact match first, then fuzzy contains / token overlap."""
        needle = (name or "").strip().lower()
        needle = re.sub(r"^(workflow|macro)\s+", "", needle).strip()
        if not needle:
            return None
        items = self.list_workflows(user_id)
        for wf in items:
            if wf["name"].lower() == needle:
                return wf

        scored: List[Tuple[int, Dict[str, Any]]] = []
        tokens = [t for t in re.split(r"\W+", needle) if len(t) > 1]
        for wf in items:
            wn = wf["name"].lower()
            score = 0
            if needle in wn or wn in needle:
                score += 50
            if tokens:
                hits = sum(1 for t in tokens if t in wn)
                score += int(40 * hits / len(tokens))
            if score > 0:
                scored.append((score, wf))
        if not scored:
            return None
        scored.sort(key=lambda x: (-x[0], len(x[1]["name"])))
        best_score, best = scored[0]
        if best_score < 30:
            return None
        return best

    def tasks_from_action_history(self, history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mapped: List[Dict[str, Any]] = []
        for item in history:
            action = item.get("action")
            if action == "open_app":
                mapped.append(
                    {
                        "intent": "open_app",
                        "target_app": item.get("app", ""),
                        "target_element": "",
                        "input_value": "",
                        "params": {},
                    }
                )
            elif action in ("open_path", "find_and_open"):
                query = item.get("matched") or item.get("path") or item.get("query") or ""
                mapped.append(
                    {
                        "intent": "open_file",
                        "target_app": "",
                        "target_element": "",
                        "input_value": str(query),
                        "params": {
                            "query": str(item.get("query") or query),
                            "path": str(item.get("path") or item.get("matched") or ""),
                            "kind": item.get("kind") or "any",
                        },
                    }
                )
            elif action == "type_text":
                mapped.append(
                    {
                        "intent": "type_text",
                        "target_app": "",
                        "target_element": "",
                        "input_value": item.get("text", ""),
                        "params": {},
                    }
                )
            elif action == "click":
                label = str(
                    item.get("label") or item.get("element") or ""
                ).strip()
                params: Dict[str, Any] = {"x": item.get("x"), "y": item.get("y")}
                if label:
                    params["label"] = label
                    params["element"] = label
                mapped.append(
                    {
                        "intent": "click_text",
                        "target_app": "",
                        "target_element": label,
                        "input_value": "",
                        "params": params,
                    }
                )
            elif action == "press":
                mapped.append(
                    {
                        "intent": "press_key",
                        "target_app": "",
                        "target_element": "",
                        "input_value": item.get("key", ""),
                        "params": {},
                    }
                )
            elif action in ("scroll", "hscroll"):
                mapped.append(
                    {
                        "intent": "scroll",
                        "target_app": "",
                        "target_element": "",
                        "input_value": "",
                        "params": {
                            "direction": item.get("direction", "down"),
                            "amount": item.get("amount", 3),
                        },
                    }
                )
            elif action == "wait":
                mapped.append(
                    {
                        "intent": "wait",
                        "target_app": "",
                        "target_element": "",
                        "input_value": str(item.get("seconds", 1)),
                        "params": {"seconds": item.get("seconds", 1)},
                    }
                )
            elif action == "search_google":
                mapped.append(
                    {
                        "intent": "search_web",
                        "target_app": "chrome",
                        "target_element": "",
                        "input_value": item.get("query", ""),
                        "params": {"query": item.get("query", ""), "url": item.get("url", "")},
                    }
                )
            elif action == "open_url":
                mapped.append(
                    {
                        "intent": "open_app",
                        "target_app": "chrome",
                        "target_element": "",
                        "input_value": item.get("url", ""),
                        "params": {"url": item.get("url", "")},
                    }
                )
            elif action == "address_bar_search":
                mapped.append(
                    {
                        "intent": "search_web",
                        "target_app": "",
                        "target_element": "",
                        "input_value": item.get("query", ""),
                        "params": {"query": item.get("query", "")},
                    }
                )
            elif action == "copy_file":
                mapped.append(
                    {
                        "intent": "copy_file",
                        "target_app": "",
                        "target_element": item.get("source") or item.get("matched_source") or "",
                        "input_value": item.get("destination") or item.get("copied_to") or "",
                        "params": {
                            "source": item.get("source") or item.get("matched_source") or "",
                            "destination": item.get("destination")
                            or item.get("copied_to")
                            or item.get("dest_resolved")
                            or "",
                        },
                    }
                )
            elif action == "move_file":
                mapped.append(
                    {
                        "intent": "move_file",
                        "target_app": "",
                        "target_element": item.get("source") or item.get("matched_source") or "",
                        "input_value": item.get("destination") or item.get("moved_to") or "",
                        "params": {
                            "source": item.get("source") or item.get("matched_source") or "",
                            "destination": item.get("destination")
                            or item.get("moved_to")
                            or item.get("dest_resolved")
                            or "",
                        },
                    }
                )
        return WorkflowService.fill_empty_clicks_after_search(mapped)

    @staticmethod
    def _task_params(task: Dict[str, Any]) -> Dict[str, Any]:
        params = task.get("params")
        if isinstance(params, dict) and params:
            return dict(params)
        raw = task.get("params_json") or "{}"
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            return dict(decoded) if isinstance(decoded, dict) else {}
        return {}

    @staticmethod
    def fill_empty_clicks_after_search(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """A click with no name after search_web means the first Google result."""
        out: List[Dict[str, Any]] = []
        after_search = False
        for task in tasks:
            item = dict(task)
            intent = str(item.get("intent") or "")
            if intent == "search_web":
                after_search = True
                out.append(item)
                continue
            if intent in ("click_text", "click_button"):
                params = WorkflowService._task_params(item)
                target = str(item.get("target_element") or "").strip()
                if not target:
                    target = str(params.get("label") or params.get("element") or "").strip()
                if not target:
                    if after_search:
                        item["target_element"] = FIRST_RESULT_ELEMENT
                        merged = dict(params)
                        merged.update(first_result_entities())
                        item["params"] = merged
                        item["params_json"] = json.dumps(merged)
                        after_search = False
                    else:
                        # Drop nameless clicks that would search for "".
                        continue
                else:
                    item["target_element"] = target
                    after_search = False
                out.append(item)
                continue
            if intent not in ("wait", "inspect_screen", "verify_screen"):
                after_search = False
            out.append(item)
        return out

    @staticmethod
    def task_to_step(task: Dict[str, Any]) -> Dict[str, Any]:
        params = WorkflowService._task_params(task)
        intent = task.get("intent", "wait")
        entities: Dict[str, Any] = dict(params) if isinstance(params, dict) else {}
        if intent == "open_app":
            entities["app"] = task.get("target_app", "") or entities.get("app", "")
            if entities.get("url") and not entities.get("app"):
                entities["app"] = "chrome"
        elif intent == "open_file":
            entities.setdefault("query", task.get("input_value") or "")
            if task.get("input_value") and not entities.get("path"):
                entities.setdefault("path", "")
        elif intent in ("click_text", "click_button"):
            entities["element"] = (
                task.get("target_element", "")
                or entities.get("element", "")
                or entities.get("label", "")
            )
            if not str(entities.get("element") or "").strip() and (
                entities.get("first_result") or entities.get("result_index")
            ):
                entities.update(first_result_entities())
                if entities.get("result_index") and int(entities.get("result_index") or 1) != 1:
                    entities["element"] = f"result {int(entities['result_index'])}"
                    entities["first_result"] = False
        elif intent == "fill_form":
            entities["field"] = task.get("target_element", "") or entities.get("field", "")
            entities["text"] = task.get("input_value", "") or entities.get("text", "")
        elif intent == "type_text":
            entities["text"] = task.get("input_value", "") or entities.get("text", "")
            if task.get("target_element"):
                entities["field"] = task.get("target_element")
        elif intent == "press_key":
            entities["key"] = task.get("input_value", "") or entities.get("key", "enter")
        elif intent == "wait":
            entities["seconds"] = float(entities.get("seconds") or task.get("input_value") or 1)
        elif intent == "search_web":
            entities["query"] = task.get("input_value", "") or entities.get("query", "")
        elif intent == "scroll":
            entities.setdefault("direction", "down")
            entities.setdefault("amount", 3)
        elif intent in ("copy_file", "move_file"):
            entities["source"] = (
                entities.get("source")
                or task.get("target_element")
                or ""
            )
            entities["destination"] = (
                entities.get("destination")
                or task.get("input_value")
                or ""
            )
        return {"intent": intent, "entities": entities, "confidence": 1.0}
