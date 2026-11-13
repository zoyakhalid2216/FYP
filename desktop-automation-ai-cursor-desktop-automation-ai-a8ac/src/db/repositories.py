"""CRUD helpers for ERD tables."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.db.database import Database, hash_password, verify_password


class UserRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def authenticate(self, username_or_email: str, password: str) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone(
            """
            SELECT * FROM User
            WHERE (username = ? OR email = ?) AND is_active = 1
            """,
            (username_or_email, username_or_email),
        )
        if not row:
            return None
        user = dict(row)
        if not verify_password(password, str(user.get("password") or "")):
            return None
        return user

    def create(self, username: str, email: str, password: str) -> int:
        cur = self.db.execute(
            "INSERT INTO User (username, email, password, is_active) VALUES (?, ?, ?, 1)",
            (username, email, hash_password(password)),
        )
        return int(cur.lastrowid)

    def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone("SELECT * FROM User WHERE user_id = ?", (user_id,))
        return dict(row) if row else None


class UserConfRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def get_map(self, user_id: int) -> Dict[str, str]:
        rows = self.db.fetchall(
            "SELECT conf_key, conf_value FROM User_Conf WHERE user_id = ?",
            (user_id,),
        )
        return {r["conf_key"]: r["conf_value"] for r in rows}

    def get(self, user_id: int, key: str, default: str = "") -> str:
        row = self.db.fetchone(
            "SELECT conf_value FROM User_Conf WHERE user_id = ? AND conf_key = ?",
            (user_id, key),
        )
        return row["conf_value"] if row else default

    def set(self, user_id: int, key: str, value: str) -> None:
        self.db.execute(
            """
            INSERT INTO User_Conf (conf_key, conf_value, user_id)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, conf_key) DO UPDATE SET conf_value = excluded.conf_value
            """,
            (key, value, user_id),
        )

    def update_many(self, user_id: int, values: Dict[str, Any]) -> None:
        for key, value in values.items():
            self.set(user_id, key, str(value))


class WorkflowRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_user(self, user_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT * FROM Workflow
            WHERE user_id = ? AND is_active = 1
            ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [dict(r) for r in rows]

    def get(self, workflow_id: int) -> Optional[Dict[str, Any]]:
        row = self.db.fetchone("SELECT * FROM Workflow WHERE workflow_id = ?", (workflow_id,))
        return dict(row) if row else None

    def create(
        self,
        user_id: int,
        name: str,
        description: str = "",
        trigger_type: str = "manual",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO Workflow (user_id, name, description, trigger_type, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (user_id, name, description, trigger_type),
        )
        return int(cur.lastrowid)

    def rename(self, workflow_id: int, name: str) -> None:
        self.db.execute("UPDATE Workflow SET name = ? WHERE workflow_id = ?", (name, workflow_id))

    def delete(self, workflow_id: int) -> None:
        self.db.execute("UPDATE Workflow SET is_active = 0 WHERE workflow_id = ?", (workflow_id,))

    def count_for_user(self, user_id: int) -> int:
        row = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM Workflow WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        return int(row["c"]) if row else 0


class TaskRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_workflow(self, workflow_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM Task WHERE workflow_id = ? ORDER BY step_order ASC",
            (workflow_id,),
        )
        return [dict(r) for r in rows]

    def replace_tasks(self, workflow_id: int, tasks: List[Dict[str, Any]]) -> None:
        self.db.execute("DELETE FROM Task WHERE workflow_id = ?", (workflow_id,))
        for idx, task in enumerate(tasks, start=1):
            params = task.get("params") or task.get("params_json") or {}
            params_json = json.dumps(params) if isinstance(params, dict) else str(params)
            self.db.execute(
                """
                INSERT INTO Task (
                    workflow_id, step_order, intent, target_app,
                    target_element, input_value, params_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workflow_id,
                    idx,
                    task.get("intent", "wait"),
                    task.get("target_app", ""),
                    task.get("target_element", ""),
                    task.get("input_value", ""),
                    params_json,
                ),
            )

    def average_steps(self, user_id: int) -> float:
        row = self.db.fetchone(
            """
            SELECT AVG(cnt) AS avg_steps FROM (
                SELECT COUNT(*) AS cnt
                FROM Task t
                JOIN Workflow w ON w.workflow_id = t.workflow_id
                WHERE w.user_id = ? AND w.is_active = 1
                GROUP BY t.workflow_id
            )
            """,
            (user_id,),
        )
        return float(row["avg_steps"] or 0) if row else 0.0


class AutomationRuleRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def list_for_workflow(self, workflow_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            """
            SELECT * FROM AutomationRule
            WHERE workflow_id = ? AND is_active = 1
            ORDER BY priority ASC
            """,
            (workflow_id,),
        )
        return [dict(r) for r in rows]

    def add(
        self,
        workflow_id: int,
        rule_name: str,
        condition: str = "{}",
        action: str = "run_workflow",
        priority: int = 100,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO AutomationRule
                (workflow_id, rule_name, condition, action, priority, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (workflow_id, rule_name, condition, action, priority),
        )
        return int(cur.lastrowid)


class NLPCommandRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        raw_text: str,
        parsed_intent: str,
        entities: Dict[str, Any],
        confidence: float,
        source: str = "text",
        user_id: Optional[int] = None,
        task_id: Optional[int] = None,
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO NLP_Command (
                user_id, task_id, raw_text, parsed_intent, entities_json, confidence, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, task_id, raw_text, parsed_intent, json.dumps(entities), confidence, source),
        )
        return int(cur.lastrowid)

    def recent(self, user_id: Optional[int] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if user_id is None:
            rows = self.db.fetchall(
                "SELECT * FROM NLP_Command ORDER BY executed_at DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self.db.fetchall(
                """
                SELECT * FROM NLP_Command
                WHERE user_id = ?
                ORDER BY executed_at DESC LIMIT ?
                """,
                (user_id, limit),
            )
        return [dict(r) for r in rows]


class ExecutionLogRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        status: str,
        duration_ms: int,
        error_message: str = "",
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        command_id: Optional[int] = None,
        action_id: str = "",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO Execution_log (
                user_id, command_id, status, duration_ms,
                error_message, action_id, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                command_id,
                status,
                duration_ms,
                error_message,
                action_id,
                json.dumps(details or {}),
            ),
        )
        return int(cur.lastrowid)

    def recent(self, user_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        if user_id is None:
            rows = self.db.fetchall(
                "SELECT * FROM Execution_log ORDER BY started_at DESC LIMIT ?",
                (limit,),
            )
        else:
            rows = self.db.fetchall(
                """
                SELECT * FROM Execution_log
                WHERE user_id = ?
                ORDER BY started_at DESC LIMIT ?
                """,
                (user_id, limit),
            )
        return [dict(r) for r in rows]

    def stats(self, user_id: int) -> Dict[str, Any]:
        total = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM Execution_log WHERE user_id = ?",
            (user_id,),
        )
        success = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM Execution_log WHERE user_id = ? AND status = 'Success'",
            (user_id,),
        )
        today = self.db.fetchone(
            """
            SELECT COUNT(*) AS c FROM Execution_log
            WHERE user_id = ? AND date(started_at) = date('now')
            """,
            (user_id,),
        )
        total_c = int(total["c"]) if total else 0
        success_c = int(success["c"]) if success else 0
        rate = (success_c / total_c * 100.0) if total_c else 100.0
        failed = self.db.fetchone(
            "SELECT COUNT(*) AS c FROM Execution_log WHERE user_id = ? AND status = 'Failed'",
            (user_id,),
        )
        avg = self.db.fetchone(
            "SELECT AVG(duration_ms) AS a FROM Execution_log WHERE user_id = ?",
            (user_id,),
        )
        daily_rows = self.db.fetchall(
            """
            SELECT date(started_at) AS d, COUNT(*) AS c
            FROM Execution_log
            WHERE user_id = ? AND started_at >= date('now', '-6 days')
            GROUP BY date(started_at)
            ORDER BY d ASC
            """,
            (user_id,),
        )
        daily = {str(r["d"]): int(r["c"]) for r in daily_rows}
        failed_c = int(failed["c"]) if failed else 0
        avg_ms = float(avg["a"] or 0) if avg else 0.0
        return {
            "total": total_c,
            "success": success_c,
            "failed": failed_c,
            "success_rate": round(rate, 1),
            "today": int(today["c"]) if today else 0,
            "avg_ms": int(avg_ms),
            "daily": daily,
        }


class ScreenCaptureRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def create(
        self,
        file_path: str,
        log_id: Optional[int] = None,
        width: int = 0,
        height: int = 0,
        element_found: str = "",
    ) -> int:
        cur = self.db.execute(
            """
            INSERT INTO Screen_capture (log_id, file_path, width, height, element_found)
            VALUES (?, ?, ?, ?, ?)
            """,
            (log_id, file_path, width, height, element_found),
        )
        return int(cur.lastrowid)

    def list_for_log(self, log_id: int) -> List[Dict[str, Any]]:
        rows = self.db.fetchall(
            "SELECT * FROM Screen_capture WHERE log_id = ? ORDER BY captured_at DESC",
            (log_id,),
        )
        return [dict(r) for r in rows]
