"""Hold incomplete Chrome/Vosk 'finals' so mid-sentence pauses never click."""

from __future__ import annotations

import re
import time
from typing import List, Optional, Tuple

from src.speech.wake import is_sleep_phrase, is_wakeup_phrase

_TRAILING = re.compile(r"\b(with|the|a|an|to|for|my|and|or|then|on)$", re.I)
_NAKED = re.compile(
    r"^(click|tap|open|go|go to|type|enter|search|press|scroll|fill|select)$",
    re.I,
)
_IMMEDIATE = re.compile(
    r"^((dai|ai)\s+)?(stop|cancel|emergency stop|done|finish|sleep|wakeup|wake up)(\s+now)?$"
    r"|^cancel task$",
    re.I,
)


def looks_incomplete(text: str) -> bool:
    t = " ".join((text or "").split()).strip(" .,!?")
    if not t:
        return True
    if _IMMEDIATE.match(t) or is_wakeup_phrase(t) or is_sleep_phrase(t, session_active=True):
        return False
    if _NAKED.match(t):
        return True
    if _TRAILING.search(t):
        return True
    return False


class SpeechFinalizer:
    """Join split finals ('click login with' + 'microsoft') before execution."""

    def __init__(self, hold_s: float = 0.55, incomplete_s: float = 0.75) -> None:
        self.hold_s = hold_s
        self.incomplete_s = incomplete_s
        self._text = ""
        self._alts: List[str] = []
        self._due = 0.0

    def clear(self) -> None:
        self._text = ""
        self._alts = []
        self._due = 0.0

    def pending(self) -> bool:
        return bool(self._text)

    @property
    def held(self) -> str:
        return self._text

    def remaining_ms(self, now: Optional[float] = None) -> int:
        clock = time.monotonic() if now is None else now
        return max(40, int((self._due - clock) * 1000))

    def feed_final(
        self,
        text: str,
        alternatives: Optional[List[str]] = None,
        *,
        now: Optional[float] = None,
    ) -> Optional[Tuple[str, List[str]]]:
        clock = time.monotonic() if now is None else now
        piece = " ".join((text or "").split())
        if not piece:
            return None
        alts = [a for a in (alternatives or []) if a]
        if self._text:
            joined = f"{self._text} {piece}".strip()
            self._text = joined
            self._alts = list(dict.fromkeys(self._alts + alts))
        else:
            self._text = piece
            self._alts = alts
        if _IMMEDIATE.match(self._text) or is_wakeup_phrase(self._text):
            return self.flush()
        if looks_incomplete(self._text):
            self._due = clock + self.incomplete_s
            return None
        if len(self._text.split()) <= 2:
            self._due = clock + self.hold_s
            return None
        return self.flush()

    def take_due(self, *, now: Optional[float] = None) -> Optional[Tuple[str, List[str]]]:
        clock = time.monotonic() if now is None else now
        if not self._text or clock < self._due:
            return None
        return self.flush()

    def flush(self) -> Optional[Tuple[str, List[str]]]:
        text = self._text
        alts = list(self._alts)
        self.clear()
        if not text:
            return None
        return text, alts
