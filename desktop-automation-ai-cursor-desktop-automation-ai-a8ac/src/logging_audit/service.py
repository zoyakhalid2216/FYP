"""Persist execution logs and screen capture metadata (ERD)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.db.database import Database
from src.db.repositories import ExecutionLogRepository, ScreenCaptureRepository


class AuditService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.logs = ExecutionLogRepository(db)
        self.captures = ScreenCaptureRepository(db)

    def log_execution(
        self,
        status: str,
        duration_ms: int,
        error_message: str = "",
        details: Optional[Dict[str, Any]] = None,
        user_id: Optional[int] = None,
        workflow_id: Optional[int] = None,
        command_id: Optional[int] = None,
        capture_paths: Optional[List[str]] = None,
        action_id: str = "",
    ) -> int:
        details = dict(details or {})
        if workflow_id is not None:
            details["workflow_id"] = workflow_id
        log_id = self.logs.create(
            status=status,
            duration_ms=duration_ms,
            error_message=error_message,
            details=details,
            user_id=user_id,
            command_id=command_id,
            action_id=action_id or (f"wf-{workflow_id}" if workflow_id else ""),
        )
        for path in capture_paths or []:
            width = height = 0
            try:
                from PIL import Image

                with Image.open(path) as im:
                    width, height = im.size
            except Exception:
                pass
            element = ""
            if isinstance(details.get("parsed"), dict):
                element = str((details["parsed"].get("entities") or {}).get("element", ""))
            self.captures.create(
                file_path=path,
                log_id=log_id,
                width=width,
                height=height,
                element_found=element,
            )
        return log_id

    def recent_logs(self, limit: int = 50, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.logs.recent(user_id=user_id, limit=limit)
