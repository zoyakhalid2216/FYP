"""Developer-facing agent log. Never writes secrets."""

from __future__ import annotations

from datetime import datetime
from typing import List

from src.agent.sensitive import redact

_LINES: List[str] = []


def agent_log(message: str) -> str:
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {redact(message)}"
    _LINES.append(line)
    if len(_LINES) > 400:
        del _LINES[:200]
    return line


def recent_logs(limit: int = 40) -> List[str]:
    return list(_LINES[-limit:])
