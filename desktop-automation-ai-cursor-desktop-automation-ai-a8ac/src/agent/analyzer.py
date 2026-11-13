"""Screen understanding: OCR words → structured buttons / links / inputs."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.elements import ScreenElement, ScreenState
from src.vision.search_result import link_bands_from_frame, list_search_results

_BUTTON_WORDS = re.compile(
    r"\b(login|log in|sign in|signin|next|continue|submit|send|search|"
    r"ok|okay|cancel|close|save|apply|download|upload|register|create|"
    r"microsoft|google|facebook|apple|yes|no)\b",
    re.I,
)
_INPUT_WORDS = re.compile(
    r"\b(email|e-mail|username|user name|password|phone|search|otp|pin)\b",
    re.I,
)
_LINK_WORDS = re.compile(r"https?://|www\.|[\w-]+\.(com|org|net|edu|pk|uk|io)\b", re.I)


def _classify_line(text: str) -> str:
    t = text or ""
    if _INPUT_WORDS.search(t) and not _BUTTON_WORDS.search(t):
        return "input"
    if _LINK_WORDS.search(t) and len(t.split()) <= 4:
        return "link"
    if _BUTTON_WORDS.search(t) or len(t.split()) <= 5:
        return "button"
    return "text"


def _span(group: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not group:
        return None
    group = sorted(group, key=lambda i: int(i.get("x") or 0))
    text = " ".join(str(i.get("label") or "") for i in group).strip()
    if not text:
        return None
    x0 = int(group[0].get("x") or 0)
    y0 = min(int(i.get("y") or 0) for i in group)
    x1 = max(int(i.get("x") or 0) + int(i.get("w") or 0) for i in group)
    y1 = max(int(i.get("y") or 0) + int(i.get("h") or 0) for i in group)
    avg = sum(float(i.get("conf") or 70) for i in group) / max(1, len(group))
    return {"text": text, "x": x0, "y": y0, "w": max(8, x1 - x0), "h": max(8, y1 - y0), "conf": avg}


def _group_lines(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Group by Tesseract lines AND by visual row so split button labels still join."""
    lines: Dict[Any, List[Dict[str, Any]]] = {}
    for item in words:
        key = (item.get("block"), item.get("line"), int(item.get("y") or 0) // 10)
        lines.setdefault(key, []).append(item)
    out = []
    seen = set()
    for group in lines.values():
        span = _span(group)
        if span and span["text"].lower() not in seen:
            seen.add(span["text"].lower())
            out.append(span)

    rows: List[Dict[str, Any]] = []
    for item in sorted(words, key=lambda w: (int(w.get("y") or 0), int(w.get("x") or 0))):
        y = int(item.get("y") or 0)
        h = max(8, int(item.get("h") or 8))
        placed = False
        for row in rows:
            if abs(y - int(row["y"])) <= max(14, int(row["h"] * 0.75)):
                row["items"].append(item)
                row["h"] = max(row["h"], h)
                n = len(row["items"])
                row["y"] = int((int(row["y"]) * (n - 1) + y) / n)
                placed = True
                break
        if not placed:
            rows.append({"y": y, "h": h, "items": [item]})
    for row in rows:
        items = row["items"]
        full = _span(items)
        if full and full["text"].lower() not in seen:
            seen.add(full["text"].lower())
            out.append(full)
        for i in range(len(items)):
            for j in range(i + 1, min(len(items), i + 4) + 1):
                span = _span(items[i:j])
                if span and span["text"].lower() not in seen:
                    seen.add(span["text"].lower())
                    out.append(span)
    out.sort(key=lambda r: (r["y"], r["x"]))
    return out


class ScreenAnalyzer:
    def __init__(self, vision) -> None:
        self.vision = vision

    def analyze(
        self,
        frame=None,
        extra_elements: Optional[List[ScreenElement]] = None,
        include_accessibility: bool = True,
    ) -> ScreenState:
        img = frame if frame is not None else self.vision.capture_screen()
        h, w = img.shape[:2]
        words = []
        if hasattr(self.vision, "_ocr_words"):
            words = self.vision._ocr_words(img)
        elements: List[ScreenElement] = []
        for i, line in enumerate(_group_lines(words)):
            kind = _classify_line(line["text"])
            elements.append(
                ScreenElement(
                    id=f"ocr-{i}",
                    type=kind,
                    text=line["text"],
                    role=kind,
                    x=line["x"],
                    y=line["y"],
                    width=line["w"],
                    height=line["h"],
                    confidence=max(0.4, min(0.98, float(line["conf"]) / 100.0)),
                    source="OCR",
                )
            )
        extra = []
        try:
            extra = link_bands_from_frame(img)
        except Exception:
            extra = []
        ranked_els: List[ScreenElement] = []
        for hit in list_search_results(words, w, h, extra_titles=extra):
            idx = int(hit.get("index") or 1)
            ranked_els.append(
                ScreenElement(
                    id=f"ocr-result-{idx}",
                    type="link",
                    text=str(hit.get("label") or f"result {idx}"),
                    role=f"result_{idx}",
                    x=int(hit["x"]),
                    y=int(hit["y"]),
                    width=int(hit["w"]),
                    height=int(hit["h"]),
                    confidence=0.9,
                    source="OCR",
                )
            )
        elements = ranked_els + elements
        path = ""
        try:
            path = self.vision.save_capture(img, label="screen_state", boxes=[e.to_dict() for e in elements[:24]])
        except Exception:
            path = ""
        if extra_elements:
            elements.extend(extra_elements)
        elif include_accessibility:
            a11y = _optional_accessibility(getattr(self.vision, "last_region", None))
            if a11y:
                elements.extend(a11y)
        return ScreenState(elements=elements, width=w, height=h, capture_path=path)


def _optional_accessibility(region: Optional[Dict[str, Any]] = None) -> List[ScreenElement]:
    """Best-effort Windows UI Automation. Soft-fail if pywinauto is not installed."""
    from src.agent.a11y import collect_elements

    return collect_elements(region)
