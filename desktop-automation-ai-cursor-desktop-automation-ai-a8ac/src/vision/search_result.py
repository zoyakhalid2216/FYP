"""Rank live Google-style results from the CURRENT screen (OCR + optional blue links)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence

FIRST_RESULT_ELEMENT = "__first_result__"

_ORDINALS = {
    "first": 1,
    "1st": 1,
    "top": 1,
    "one": 1,
    "second": 2,
    "2nd": 2,
    "two": 2,
    "third": 3,
    "3rd": 3,
    "three": 3,
    "fourth": 4,
    "4th": 4,
    "four": 4,
    "fifth": 5,
    "5th": 5,
    "five": 5,
}

_WHICH = (
    r"(?P<which>first|second|third|fourth|fifth|top|1st|2nd|3rd|4th|5th|"
    r"one|two|three|four|five|\d+(?:st|nd|rd|th)?)"
)
_RESULT_NOUN = r"(?:search\s+)?(?:results?|links?|hits?|ones?|items?|listing|website|site)"

_RESULT_PHRASE = re.compile(
    r"\b(?:(?:click|tap|open|select|choose|pick|press|go\s+to)\s+)?"
    r"(?:on\s+)?(?:the\s+)?(?:number\s+)?"
    + _WHICH
    + r"\s+"
    + _RESULT_NOUN
    + r"\b",
    re.I,
)
_RESULT_ONLY = re.compile(
    r"^(?:on\s+)?(?:the\s+)?"
    + _WHICH
    + r"\s+"
    + _RESULT_NOUN
    + r"$",
    re.I,
)
_RESULT_AFTER = re.compile(
    r"\b(?:result|link|hit)s?\s+(?:number\s+|no\.?\s+|#\s*)?"
    r"(?P<which>first|second|third|fourth|fifth|one|two|three|four|five|\d+(?:st|nd|rd|th)?)\b",
    re.I,
)
_THE_ONE = re.compile(
    r"\b(?:the\s+)?" + _WHICH + r"\s+one\b",
    re.I,
)
_NUMBER_N = re.compile(
    r"\bnumbers?\s+(?P<which>one|two|three|four|five|first|second|third|fourth|fifth|\d+)\b",
    re.I,
)

_SKIP_LINE = re.compile(
    r"(dai\b|google mic|wakeup|sleeping|heard:|do you mean|"
    r"ai overview|people also ask|sponsored|about this result|"
    r"^all$|^images$|^videos$|^maps$|^news$|^shopping$|^forums$|^more$|"
    r"^tools$|^settings$|^sign in$|^gmail$|^search$|^app$|"
    r"^all images$|^all images forums$|"
    r"translations?|feedback|missing:|did you mean)",
    re.I,
)

_URLISH = re.compile(
    r"(https?://)|(\b[\w-]+\.(com|org|net|edu|pk|uk|io|gov|co|info)\b)",
    re.I,
)

_TITLE_HINT = re.compile(
    r"\b(login|log in|sign in|portal|student|official|home|dashboard|result)\b",
    re.I,
)


def _which_to_index(which: str) -> Optional[int]:
    w = (which or "").strip().lower()
    if w in _ORDINALS:
        return _ORDINALS[w]
    m = re.match(r"(\d+)", w)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 9:
            return n
    return None


def parse_result_index(text: str) -> Optional[int]:
    """Return 1-based result index from speech, or None if this is not a ranked-result command."""
    t = " ".join((text or "").lower().split())
    if not t:
        return None
    if t in {
        FIRST_RESULT_ELEMENT,
        "1",
        "first",
        "first result",
        "first link",
        "first one",
        "the first one",
        "top result",
        "top link",
    }:
        return 1
    for pat in (_RESULT_ONLY, _RESULT_PHRASE, _RESULT_AFTER, _THE_ONE, _NUMBER_N):
        m = pat.search(t) if pat is not _RESULT_ONLY else pat.match(t)
        if m:
            idx = _which_to_index(m.group("which"))
            if idx:
                return idx
    return None


def is_first_result_phrase(text: str) -> bool:
    return parse_result_index(text) == 1


def is_ranked_result_phrase(text: str) -> bool:
    return parse_result_index(text) is not None


_BARE_CLICK = re.compile(
    r"^(?:please\s+|just\s+)?(?:click|tap)(?:\s+(?:on\s+)?(?:it|that|this|here))?[.!?]*$",
    re.I,
)


def is_bare_click_phrase(text: str) -> bool:
    """True for leftover 'click' / 'click it' with no button name."""
    t = " ".join((text or "").lower().split())
    return bool(_BARE_CLICK.match(t))


def first_result_entities() -> Dict[str, Any]:
    return ranked_result_entities(1)


def ranked_result_entities(index: int = 1) -> Dict[str, Any]:
    idx = max(1, min(9, int(index or 1)))
    if idx == 1:
        return {
            "element": FIRST_RESULT_ELEMENT,
            "first_result": True,
            "result_index": 1,
        }
    return {
        "element": f"result {idx}",
        "first_result": False,
        "result_index": idx,
    }


def text_matches_query(ocr_text: str, query: str) -> bool:
    """True when an OCR fragment is a real match, not a short substring like 'the'."""
    from src.vision.ocr_text import distinctive_tokens, normalize_ocr_query

    text_l = normalize_ocr_query(ocr_text)
    query_l = normalize_ocr_query(query)
    if not text_l or not query_l:
        return False
    if query_l == text_l or query_l in text_l:
        return True
    if len(text_l) >= 5 and text_l in query_l:
        return True
    q_brands = set(distinctive_tokens(query_l))
    if q_brands and q_brands & set(re.findall(r"[a-z0-9]+", text_l)):
        return True
    return False


def _rows_from_words(words: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lines: Dict[Any, List[Dict[str, Any]]] = {}
    for item in words:
        y = int(item.get("y") or 0)
        key = (item.get("block"), item.get("line"), y // 12)
        lines.setdefault(key, []).append(item)
    ordered: List[Dict[str, Any]] = []
    for group in lines.values():
        group.sort(key=lambda i: int(i.get("x") or 0))
        text = " ".join(str(i.get("label") or "") for i in group).strip()
        if not text:
            continue
        x0 = int(group[0].get("x") or 0)
        y0 = min(int(i.get("y") or 0) for i in group)
        x1 = max(int(i.get("x") or 0) + int(i.get("w") or 0) for i in group)
        y1 = max(int(i.get("y") or 0) + int(i.get("h") or 0) for i in group)
        ordered.append(
            {
                "text": text,
                "x": x0,
                "y": y0,
                "w": max(8, x1 - x0),
                "h": max(8, y1 - y0),
            }
        )
    ordered.sort(key=lambda line: (line["y"], line["x"]))
    return ordered


def _looks_like_title(text: str) -> bool:
    t = " ".join((text or "").split())
    if len(t) < 4 or _URLISH.search(t) or _SKIP_LINE.search(t):
        return False
    words = t.split()
    if len(words) > 12:
        return False
    return len(words) >= 2 or len(t) >= 8


def _title_score(text: str) -> int:
    score = 1
    if _TITLE_HINT.search(text or ""):
        score += 3
    n = len((text or "").split())
    if 2 <= n <= 6:
        score += 2
    if re.search(r"university of|colleges$|wikipedia", text or "", re.I):
        score -= 1
    return score


def _as_box(line: Dict[str, Any], *, index: int = 0) -> Dict[str, Any]:
    return {
        "x": int(line["x"]),
        "y": int(line["y"]),
        "w": int(line["w"]),
        "h": int(line["h"]),
        "label": line.get("text") or line.get("label") or f"result {index}",
        "index": index,
    }


def list_search_results(
    words: List[Dict[str, Any]],
    width: int,
    height: int,
    *,
    extra_titles: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Return organic result titles top-to-bottom from the live screen."""
    if width <= 0 or height <= 0:
        return []
    chrome_cut = 72
    bot_cut = int(height * 0.92)
    right_cut = int(width * 0.80)

    rows = []
    for line in _rows_from_words(words or []):
        if line["y"] < chrome_cut or line["y"] > bot_cut or line["x"] > right_cut:
            continue
        if _SKIP_LINE.search(line["text"]):
            continue
        rows.append(line)

    results: List[Dict[str, Any]] = []
    used = set()

    def add_title(line: Dict[str, Any]) -> None:
        key = (round(line["y"] / 20), " ".join(line["text"].lower().split())[:40])
        if key in used:
            return
        used.add(key)
        results.append(_as_box(line, index=len(results) + 1))

    urls = [i for i, row in enumerate(rows) if _URLISH.search(row["text"])]
    for ui in urls:
        url = rows[ui]
        # Isolated URL in the search-box strip is not a result.
        if url["y"] < 130 and not any(
            _looks_like_title(rows[j]["text"]) and abs(rows[j]["y"] - url["y"]) < 70
            for j in range(len(rows))
            if j != ui
        ):
            continue
        candidates = []
        for j, row in enumerate(rows):
            if j == ui or not _looks_like_title(row["text"]):
                continue
            dist = row["y"] - url["y"]
            if abs(dist) > 90:
                continue
            # Prefer a title just below the URL (current Google) or just above (classic).
            prefer = 0 if 0 <= dist <= 70 else (1 if -70 <= dist < 0 else 3)
            candidates.append((_title_score(row["text"]) * 10 - prefer * 3 - abs(dist) // 10, row))
        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            add_title(candidates[0][1])
        else:
            add_title(url)

    if not results:
        for row in rows:
            if _looks_like_title(row["text"]):
                add_title(row)

    for extra in extra_titles or []:
        text = str(extra.get("label") or extra.get("text") or "").strip()
        box = {
            "text": text or "search result",
            "x": int(extra.get("x") or 0),
            "y": int(extra.get("y") or 0),
            "w": int(extra.get("w") or extra.get("width") or 40),
            "h": int(extra.get("h") or extra.get("height") or 18),
        }
        if box["y"] < chrome_cut:
            continue
        add_title(box)

    results.sort(key=lambda r: (r["y"], r["x"]))
    for i, item in enumerate(results, start=1):
        item["index"] = i
    return results[:8]


def pick_search_result(
    words: List[Dict[str, Any]],
    width: int,
    height: int,
    index: int = 1,
    *,
    extra_titles: Optional[Sequence[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    ranked = list_search_results(words, width, height, extra_titles=extra_titles)
    if 1 <= int(index) <= len(ranked):
        return ranked[int(index) - 1]
    return None


def pick_first_search_result(
    words: List[Dict[str, Any]],
    width: int,
    height: int,
) -> Optional[Dict[str, Any]]:
    return pick_search_result(words, width, height, index=1)


def link_bands_from_frame(frame) -> List[Dict[str, Any]]:
    """Find Google-style blue/cyan title rows (works in dark mode when OCR is weak)."""
    try:
        import numpy as np
    except Exception:
        return []
    if frame is None:
        return []
    img = np.asarray(frame)
    if img.ndim != 3 or img.shape[0] < 40:
        return []
    h, w = img.shape[:2]
    r = img[:, :, 0].astype("int16")
    g = img[:, :, 1].astype("int16")
    b = img[:, :, 2].astype("int16")
    # Dark-mode Google links (~#8ab4f8), classic blue titles, visited purple.
    dark_mode = (b > 170) & (g > 125) & (r < 200) & (b > r + 15)
    classic = (b > 145) & (r < 95) & (g < 155) & (b > g)
    visited = (r > 120) & (b > 150) & (g < 140) & (b > r)
    mask = dark_mode | classic | visited
    left = int(w * 0.06)
    right = int(w * 0.72)
    top = 90
    bands: List[Dict[str, Any]] = []
    y = top
    while y < int(h * 0.88):
        row = mask[y, left:right]
        if int(row.sum()) > max(18, int((right - left) * 0.04)):
            y1 = y
            while y1 < h - 1 and int(mask[y1, left:right].sum()) > 10:
                y1 += 1
                if y1 - y > 36:
                    break
            height = max(14, y1 - y)
            xs = []
            for yy in range(y, min(h, y + height)):
                cols = mask[yy, left:right]
                if cols.any():
                    found = cols.nonzero()[0]
                    xs.append(int(found[0] + left))
                    xs.append(int(found[-1] + left))
            if xs:
                x0, x1 = min(xs), max(xs)
                if x1 - x0 >= 40:
                    bands.append(
                        {
                            "x": x0,
                            "y": y,
                            "w": max(40, x1 - x0),
                            "h": height,
                            "label": "search result",
                        }
                    )
            y = y1 + 8
        else:
            y += 2
    # Merge bands that are stacked on the same result title.
    merged: List[Dict[str, Any]] = []
    for band in bands:
        if merged and abs(band["y"] - (merged[-1]["y"] + merged[-1]["h"])) < 10:
            prev = merged[-1]
            prev["h"] = band["y"] + band["h"] - prev["y"]
            prev["x"] = min(prev["x"], band["x"])
            prev["w"] = max(prev["x"] + prev["w"], band["x"] + band["w"]) - prev["x"]
        else:
            merged.append(dict(band))
    return merged[:8]
