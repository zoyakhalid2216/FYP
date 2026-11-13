"""OS-level mouse/keyboard automation."""

from src.automation.engine import AutomationEngine
from src.automation.safety import SafetyLimitError, SafetyPolicy

__all__ = ["AutomationEngine", "SafetyLimitError", "SafetyPolicy"]
