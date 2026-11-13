"""Turn half-heard speech into on-screen “Do you mean this?” choices."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import List, Sequence

from src.nlp.engine import NLPEngine

TEMPLATES = [
    "Open Chrome",
    "Open Notepad",
    "Open File Explorer",
    "Open Downloads",
    "Open Calculator",
    "Minimize this window",
    "Minimize all windows",
    "Restore windows",
    "Click Login",
    "Click Submit",
    "Click OK",
    "Double click",
    "Type hello",
    "Search Google",
    "Search YouTube",
    "Copy this file to Desktop",
    "Paste here",
    "Select all",
    "Save this",
    "Close this window",
    "Scroll down",
    "Scroll up",
    "Take a screenshot",
    "Go to Agent",
    "Go to Voice",
]

INCOMPLETE_VERBS = {
    "open": ["Open Chrome", "Open Notepad", "Open File Explorer", "Open Downloads"],
    "launch": ["Open Chrome", "Open Notepad"],
    "click": ["Click Login", "Click Submit", "Click OK"],
    "tap": ["Click Login", "Click Submit"],
    "search": ["Search Google", "Search YouTube"],
    "type": ["Type hello", "Type the text"],
    "write": ["Type hello"],
    "run": ["Run my workflow"],
    "copy": ["Copy this file to Desktop"],
    "paste": ["Paste here"],
    "go": ["Go to Agent", "Go to Voice"],
    "close": ["Close this window"],
    "minimize": ["Minimize this window"],
    "minimise": ["Minimize this window"],
    "restore": ["Restore windows"],
    "scroll": ["Scroll down", "Scroll up"],
}

_ENGINE = NLPEngine(lazy=True)


@dataclass
class ClarifyResult:
    needed: bool
    heard: str
    suggestions: List[str] = field(default_factory=list)


def _title_case_command(text: str) -> str:
    t = " ".join((text or "").split())
    if not t:
        return ""
    return t[:1].upper() + t[1:]


def _unique(items: Sequence[str], *, limit: int = 4) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        key = " ".join((item or "").split()).strip()
        if not key:
            continue
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(_title_case_command(key))
        if len(out) >= limit:
            break
    return out


def _looks_incomplete(text: str) -> bool:
    words = (text or "").lower().split()
    if not words:
        return True
    if len(words) == 1:
        return True
    if words[0] in INCOMPLETE_VERBS and len(words[1]) <= 4:
        return True
    return False


def _grammar_completions(text: str) -> List[str]:
    low = " ".join((text or "").lower().split())
    if not low:
        return list(TEMPLATES[:4])
    words = low.split()
    out: List[str] = []
    if words[0] in INCOMPLETE_VERBS:
        rest = " ".join(words[1:])
        for tmpl in INCOMPLETE_VERBS[words[0]]:
            if not rest or rest in tmpl.lower() or tmpl.lower().startswith(low):
                out.append(tmpl)
        for tmpl in TEMPLATES:
            if tmpl.lower().startswith(words[0]) and rest and rest in tmpl.lower():
                out.insert(0, tmpl)
    lowered = [t.lower() for t in TEMPLATES]
    close = difflib.get_close_matches(low, lowered, n=4, cutoff=0.42)
    for hit in close:
        for tmpl in TEMPLATES:
            if tmpl.lower() == hit:
                out.append(tmpl)
                break
    # Prefix match: "open chro" → Open Chrome
    for tmpl in TEMPLATES:
        tl = tmpl.lower()
        if tl.startswith(low) or low.startswith(tl.split()[0]) and low in tl:
            out.append(tmpl)
    return out


def clarify_heard(text: str, alternatives: Sequence[str] | None = None) -> ClarifyResult:
    heard = " ".join((text or "").split())
    alts = [_title_case_command(a) for a in (alternatives or []) if str(a).strip()]
    if not heard:
        return ClarifyResult(needed=False, heard="", suggestions=[])

    parsed = _ENGINE.parse(heard)
    incomplete = _looks_incomplete(heard)
    suggestions: List[str] = []

    for alt in alts:
        if alt.lower() == heard.lower():
            continue
        p = _ENGINE.parse(alt)
        if p.intent not in ("unknown", "help") and p.confidence >= 0.55:
            suggestions.append(alt)

    suggestions.extend(_grammar_completions(heard))

    if parsed.intent not in ("unknown", "help") and parsed.confidence >= 0.75 and not incomplete:
        return ClarifyResult(needed=False, heard=heard, suggestions=[])

    if incomplete or parsed.intent in ("unknown", "help") or parsed.confidence < 0.7:
        uniq = _unique(suggestions, limit=4)
        if heard.lower() not in {s.lower() for s in uniq} and incomplete:
            # Offer the raw heard line as a last chip so the user can still confirm.
            extra = _title_case_command(heard)
            if extra and not re.match(r"^(open|click|search|type|run|copy|go)$", extra, re.I):
                uniq = _unique(list(uniq) + [extra], limit=4)
        if not uniq:
            uniq = [_title_case_command(heard)]
        return ClarifyResult(needed=True, heard=heard, suggestions=uniq)

    return ClarifyResult(needed=False, heard=heard, suggestions=[])
