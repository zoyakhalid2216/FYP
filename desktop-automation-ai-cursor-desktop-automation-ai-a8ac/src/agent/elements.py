"""Screen element + screen-state schemas."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


SOURCES = ("ACCESSIBILITY", "DOM", "OCR", "VISION")


@dataclass
class ScreenElement:
    id: str
    type: str
    text: str = ""
    role: str = ""
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    enabled: bool = True
    visible: bool = True
    source: str = "OCR"
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def center(self) -> tuple:
        return self.x + self.width // 2, self.y + self.height // 2

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["cx"], data["cy"] = self.center
        return data


@dataclass
class ScreenState:
    elements: List[ScreenElement] = field(default_factory=list)
    width: int = 0
    height: int = 0
    url: str = ""
    application: str = ""
    capture_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "elements": [e.to_dict() for e in self.elements],
            "width": self.width,
            "height": self.height,
            "url": self.url,
            "application": self.application,
            "capture_path": self.capture_path,
        }

    def by_text(self, query: str) -> Optional[ScreenElement]:
        q = (query or "").lower().strip()
        for el in self.elements:
            if q and q in (el.text or "").lower():
                return el
        return None
