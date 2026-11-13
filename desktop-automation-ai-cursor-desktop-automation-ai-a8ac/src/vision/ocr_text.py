"""OCR cleanup so brand buttons still match when Tesseract misreads them."""

from __future__ import annotations

import re
from typing import Iterable, List

_BRANDS = (
    (re.compile(r"m[il1]cro\s*s[o0][fli1t]{1,4}", re.I), "microsoft"),
    (re.compile(r"micro\s+soft", re.I), "microsoft"),
    (re.compile(r"\bod[o0]{2}\b", re.I), "odoo"),
)

_BRAND_TOKENS = frozenset(
    {"microsoft", "odoo", "google", "facebook", "apple", "username", "password"}
)
_QUERY_FILLER = re.compile(
    r"\b(the|a|an|please|button|buttons|btn|link|links|icon|icons)\b",
    re.I,
)
_QUERY_STOP = frozenset(
    {
        "button",
        "buttons",
        "btn",
        "link",
        "links",
        "click",
        "tap",
        "icon",
        "the",
        "with",
        "and",
        "please",
    }
)


def normalize_ocr_text(text: str) -> str:
    t = " ".join((text or "").split())
    for pat, repl in _BRANDS:
        t = pat.sub(repl, t)
    return t


def normalize_ocr_query(text: str) -> str:
    t = normalize_ocr_text(text).lower()
    t = re.sub(r"^(click|tap|press|open|select|choose|pick)\s+(on\s+)?(the\s+)?", "", t).strip()
    t = _QUERY_FILLER.sub(" ", t)
    return " ".join(t.split()).strip()


def distinctive_tokens(text: str) -> List[str]:
    toks = re.findall(r"[a-z0-9]+", normalize_ocr_query(text))
    return [t for t in toks if t not in _QUERY_STOP and (t in _BRAND_TOKENS or len(t) >= 6)]


def brand_tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", normalize_ocr_query(text))) & _BRAND_TOKENS


def tokens_overlap(query: str, text: str) -> float:
    q = set(re.findall(r"[a-z0-9]+", normalize_ocr_query(query)))
    t = set(re.findall(r"[a-z0-9]+", normalize_ocr_query(text)))
    if not q or not t:
        return 0.0
    brands = q & t & _BRAND_TOKENS
    if brands:
        return 1.0
    return len(q & t) / max(1, len(q))


def merge_ocr_words(passes: Iterable[List[dict]]) -> List[dict]:
    merged: List[dict] = []
    for words in passes:
        for item in words:
            label = normalize_ocr_text(str(item.get("label") or ""))
            if not label:
                continue
            x, y = int(item.get("x") or 0), int(item.get("y") or 0)
            dup = False
            for prev in merged:
                if abs(int(prev["x"]) - x) <= 12 and abs(int(prev["y"]) - y) <= 10:
                    if label.lower() == str(prev.get("label") or "").lower():
                        if float(item.get("conf") or 0) > float(prev.get("conf") or 0):
                            prev.update({**item, "label": label})
                        dup = True
                        break
            if not dup:
                row = dict(item)
                row["label"] = label
                merged.append(row)
    return merged
