"""Safety limits: max actions, wall-clock timeout, retries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


class SafetyLimitError(RuntimeError):
    """Raised when an automation would exceed configured safety bounds."""


@dataclass
class SafetyPolicy:
    max_actions: int = 30
    max_seconds: float = 60.0
    max_retries: int = 3
    retry_delay: float = 0.45
    verify_change: bool = True

    @classmethod
    def from_config(cls, config: Dict[str, Any], conf: Dict[str, Any] | None = None) -> "SafetyPolicy":
        auto = (config or {}).get("automation", {})
        user = conf or {}

        def _num(key: str, default: float, cast=float):
            raw = user.get(key, auto.get(key, default))
            try:
                return cast(raw)
            except (TypeError, ValueError):
                return default

        return cls(
            max_actions=int(_num("max_actions", auto.get("max_actions", 30), int)),
            max_seconds=float(_num("max_seconds", auto.get("max_seconds", 60.0))),
            max_retries=int(_num("max_retries", auto.get("max_retries", 3), int)),
            retry_delay=float(_num("retry_delay", auto.get("retry_delay", 0.45))),
            verify_change=str(user.get("verify_actions", auto.get("verify_actions", "1"))).lower()
            in ("1", "true", "yes"),
        )

    def check_actions(self, count: int) -> None:
        if count > int(self.max_actions):
            raise SafetyLimitError(
                f"Safety limit reached: maximum {self.max_actions} actions per command."
            )

    def check_time(self, elapsed_s: float) -> None:
        if elapsed_s > float(self.max_seconds):
            raise SafetyLimitError(
                f"Safety limit reached: maximum {int(self.max_seconds)} seconds per command."
            )
