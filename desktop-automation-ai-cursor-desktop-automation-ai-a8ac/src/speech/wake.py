"""Wake-word helpers for the always-on listener (no network)."""

from __future__ import annotations

import json
import re
from typing import List, Literal, Tuple

Kind = Literal["ignore", "wake", "command", "close", "minimize", "restore", "repeat"]

DEFAULT_AGENT_NAME = "AI"
_BLOCKED_NAMES = {
    "open",
    "click",
    "stop",
    "sleep",
    "type",
    "search",
    "google",
    "chrome",
    "close",
    "cancel",
}

# "AI" is often heard as "a i", "a.i.", "ay eye", "a eye", "eye" etc.
# "DAI" legacy aliases kept for backward compat: die / dye / they / day / guy.
_DAI_CORE = r"(?:d\.?\s*a\.?\s*i\.?|dai|die|dye)"
_DAI_LOOSE = r"(?:d\.?\s*a\.?\s*i\.?|dai|die|dye|they|day|guy)"

# AI wake-word variants that STT engines commonly produce
_AI_CORE = (
    r"(?:"
    r"a\.?\s*i\.?"          # AI, A.I., A I, a i, a.i., a. i.
    r"|ay\s+eye"            # ay eye
    r"|a\s+eye"             # a eye
    r"|eye"                 # eye (only at utterance start, guarded at match site)
    r")"
)
_AI_LOOSE = (
    r"(?:"
    r"a\.?\s*i\.?"
    r"|ay\s+eye"
    r"|a\s+eye"
    r"|eye"
    r"|hey\s+i"             # hey I — common misrecognition
    r")"
)

_WAKEUP_TAIL = r"(?:wake\s*up|wakeup|wake)"
_PREFIX = r"(?:hey\s+|ok\s+|okay\s+|yo\s+)?"

_agent_name = DEFAULT_AGENT_NAME
_WAKE_CORE = _AI_CORE
_WAKE = rf"{_PREFIX}{_WAKE_CORE}"
_WAKE_CLOSE = rf"{_PREFIX}{_AI_LOOSE}"
WAKE_GRAMMAR = "[]"


def agent_name() -> str:
    return _agent_name


def sanitize_agent_name(name: str) -> str:
    raw = " ".join((name or "").split())
    raw = re.sub(r"[^A-Za-z0-9 ]+", "", raw).strip()
    if not raw or raw.lower() in _BLOCKED_NAMES:
        return DEFAULT_AGENT_NAME
    if len(raw) > 24:
        raw = raw[:24].strip()
    if len(raw) < 2:
        return DEFAULT_AGENT_NAME
    return raw


def _name_pattern(name: str) -> str:
    """Build a regex core that matches the agent name and its STT misrecognitions."""
    nl = name.lower().strip()
    # Special handling for "AI" — many STT outputs
    if nl == "ai":
        return _AI_CORE
    parts = [re.escape(p) for p in nl.split() if p]
    if not parts:
        return _DAI_CORE
    spaced = r"\s+".join(parts)
    compact = re.escape("".join(nl.split()))
    cores = [spaced]
    if compact != spaced:
        cores.append(compact)
    # Always keep DAI as a backward-compat fallback
    if nl != "dai":
        cores.append(_DAI_CORE)
    else:
        return _DAI_CORE
    return "(?:" + "|".join(cores) + ")"


def _grammar_phrases(name: str) -> List[str]:
    n = name.lower()
    phrases = [
        n,
        f"hey {n}",
        f"ok {n}",
        f"okay {n}",
        f"yo {n}",
        f"{n} wakeup",
        f"{n} wake up",
        f"{n} wake",
        f"wake up {n}",
        f"wakeup {n}",
        f"hey {n} wakeup",
        f"hey {n} wake up",
        f"{n} sleep",
        f"{n} close now",
        "[unk]",
    ]
    # Always include DAI as a backward-compat phrase
    if n not in ("dai",):
        phrases.extend(
            [
                "dai",
                "hey dai",
                "dai wakeup",
                "dai wake up",
                "wake up dai",
                "dai sleep",
                "dai close now",
            ]
        )
    # For the "AI" wake word, add all STT variant phrases
    if n == "ai":
        phrases.extend(
            [
                "a i",
                "a.i.",
                "ay eye",
                "a eye",
                "hey ai",
                "okay ai",
                "ok ai",
                "hey a i",
                "hey i",
                "eye",
                "ai stop",
                "a i stop",
            ]
        )
    # DAI-specific homophones
    if n == "dai":
        phrases.extend(
            [
                "die",
                "dye",
                "they",
                "day",
                "guy",
                "die wakeup",
                "die wake up",
                "day wakeup",
                "they wakeup",
                "die close now",
                "they close now",
                "hey dai close now",
            ]
        )
    # unique, keep order
    out, seen = [], set()
    for p in phrases:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def set_agent_name(name: str) -> str:
    """Apply a user-chosen wake name. DAI remains a backup wake word."""
    global _agent_name, _WAKE_CORE, _WAKE, _WAKE_CLOSE, WAKE_GRAMMAR
    cleaned = sanitize_agent_name(name)
    _agent_name = cleaned
    nl = cleaned.lower()
    if nl == "ai":
        _WAKE_CORE = _AI_CORE
        _WAKE = rf"{_PREFIX}(?:{_AI_CORE}|{_DAI_CORE})"
        _WAKE_CLOSE = rf"{_PREFIX}(?:{_AI_LOOSE}|{_DAI_LOOSE})"
    elif nl == "dai":
        _WAKE_CORE = _DAI_CORE
        _WAKE = rf"{_PREFIX}{_DAI_CORE}"
        _WAKE_CLOSE = rf"{_PREFIX}{_DAI_LOOSE}"
    else:
        _WAKE_CORE = _name_pattern(cleaned)
        _WAKE = rf"{_PREFIX}{_WAKE_CORE}"
        _WAKE_CLOSE = rf"{_PREFIX}(?:{_WAKE_CORE}|{_DAI_LOOSE})"
    WAKE_GRAMMAR = json.dumps(_grammar_phrases(cleaned))
    return _agent_name


set_agent_name(DEFAULT_AGENT_NAME)


def normalize(text: str) -> str:
    t = " ".join((text or "").lower().split())
    # DAI legacy normalisations
    t = t.replace("d a i", "dai").replace("d.a.i", "dai")
    t = t.replace("d.i", "dai")
    # AI normalisations: "a. i." / "a.i." -> "ai", "a i" -> "ai" only when standalone
    t = re.sub(r"\ba\.?\s*i\.?\b", "ai", t)
    # "ay eye" / "a eye" -> "ai"
    t = re.sub(r"\b(ay\s+eye|a\s+eye)\b", "ai", t)
    return t.strip(" .,!?")


def clean_spoken_command(text: str) -> str:
    """Strip politeness / STT fillers so NLP hits more often."""
    t = normalize(text)
    t = re.sub(
        r"^(please|pls|just|now|um|uh|so|okay|ok|can you|could you|would you|"
        r"i want you to|i need you to|you should|i am saying|i'm saying|"
        r"go ahead and|kindly|basically)\s+",
        "",
        t,
    )
    t = re.sub(r"^(please|can you|could you)\s+", "", t)
    t = re.sub(r"\b(for me|please)\b", "", t)
    t = re.sub(r"^(execute|run command|do this|do that)\s+", "", t)
    return " ".join(t.split()).strip(" .,!?")


_wake_aliases: List[str] = [
    "ai",
    "a i",
    "a.i.",
    "a. i.",
    "ay eye",
    "a eye",
    "hey ai",
    "hey a i",
    "okay ai",
    "ok ai",
    "hey i",
    "dai",
]


def set_wake_aliases(aliases: List[str]) -> None:
    global _wake_aliases
    if aliases:
        _wake_aliases = [normalize(a) for a in aliases if a]


def wake_aliases() -> List[str]:
    return list(_wake_aliases)


def is_close_phrase(text: str, *, session_active: bool = False) -> bool:
    t = normalize(text)
    if not t:
        return False
    if re.search(r"\bstop\b", t):
        return False
    if re.search(rf"^{_WAKE_CLOSE}\s+(close(\s+now)?|quit|sleep)$", t):
        return True
    if re.search(r"\bclose\s+now\b", t) and re.search(rf"^{_WAKE_CLOSE}\b", t):
        return True
    named = re.escape(_agent_name.lower())
    if session_active and re.search(
        rf"^(close\s+now|stop\s+listening|go\s+to\s+sleep|sleep(\s+now)?|dai sleep|ai sleep|{named} sleep)$",
        t,
    ):
        return True
    return False


def is_sleep_phrase(text: str, *, session_active: bool = False) -> bool:
    """Put assistant back to sleep until the next wake word."""
    t = normalize(text)
    if not t:
        return False
    if re.search(r"\bstop\b", t):
        return False
    if is_close_phrase(t, session_active=session_active):
        return True
    if re.search(rf"^{_WAKE_CLOSE}\s+(sleep|standby|rest)$", t):
        return True
    if session_active and re.search(
        r"^(sleep|go\s+to\s+sleep|go\s+sleep|sleep\s+now|standby)$", t
    ):
        return True
    return False


def is_wakeup_phrase(text: str) -> bool:
    """True for “AI wakeup” / “DAI wakeup”."""
    t = normalize(text)
    if not t:
        return False
    if re.search(rf"{_WAKE_CLOSE}\s+{_WAKEUP_TAIL}\b", t):
        return True
    if re.search(rf"\b{_WAKEUP_TAIL}\s+{_WAKE_CORE}\b", t):
        return True
    if _agent_name.lower() in ("ai", "dai") and re.search(rf"\b{_WAKEUP_TAIL}\s+(?:they|day|guy)\b", t):
        return True
    compact = t.replace(" ", "")
    if "wakeup" in compact or "wake up" in t:
        named = re.escape(_agent_name.lower())
        if re.search(rf"\b(?:ai|dai|die|dye|hey|{named})\b", t):
            return True
        if re.search(r"\b(?:they|day|guy)\b", t):
            return True
    return False


def is_wakeup_followup(text: str) -> bool:
    """Second half when engine splits wake word and “wakeup” into two results."""
    t = normalize(text)
    return bool(re.match(rf"^{_WAKEUP_TAIL}$", t))


def looks_like_wakeup_progress(text: str) -> bool:
    """Idle partials that look like the person is saying AI / DAI wakeup."""
    t = normalize(text)
    if not t:
        return False
    if is_wakeup_phrase(t) or is_wake_phrase(t) or is_wakeup_followup(t):
        return True
    named = re.escape(_agent_name.lower())
    return bool(re.search(rf"\b(ai|dai|die|dye|wake|{named})\b", t))


def strip_wakeup(text: str) -> str:
    t = normalize(text)
    t = re.sub(rf"^{_WAKE}\s+{_WAKEUP_TAIL}\s*", "", t)
    t = re.sub(rf"^{_WAKEUP_TAIL}\s+(?:{_WAKE_CORE}|{_DAI_CORE}|{_DAI_LOOSE})\s*", "", t)
    t = re.sub(rf"^{_WAKE_CLOSE}\s+{_WAKEUP_TAIL}\s*", "", t)
    return clean_spoken_command(t.strip(" .,!?"))


def is_wake_phrase(text: str) -> bool:
    t = normalize(text)
    if not t:
        return False

    # "eye" only when at the start of the utterance AND followed by a command
    if t == "eye":
        return False
    if re.match(r"^eye\s+[a-z0-9]", t):
        return True

    # "hey i" is accepted alone or with command
    if re.match(r"^(?:hey\s+i|ok\s+i|okay\s+i)(?:\s+.*)?$", t):
        return True

    # Whole-utterance aliases Vosk often produces instead of "DAI"
    if t in (
        "they",
        "day",
        "guy",
        "tie",
        "thai",
        "tai",
        "diet",
        "hey they",
        "ok they",
        "okay they",
        "yo they",
        "hey day",
        "hey die",
        "hey guy",
    ):
        return True

    # Check registered wake aliases (must match at start of utterance)
    for alias in _wake_aliases:
        a = normalize(alias)
        if a and (t == a or t.startswith(a + " ")):
            return True

    # Main wake pattern strictly anchored at start of utterance
    return bool(re.match(rf"^{_WAKE}\b", t))


def looks_complete_wake(text: str) -> bool:
    """Idle partial that is already wake word or wakeup phrase."""
    t = normalize(text)
    if not t:
        return False
    if is_sleep_phrase(t, session_active=False):
        return True
    if is_wakeup_phrase(t):
        return True
    if is_wake_phrase(t):
        leftover = strip_wake(t)
        if not leftover:
            return True
        return leftover == t or looks_complete_command(leftover)
    return False


def is_minimize_phrase(text: str) -> bool:
    t = clean_spoken_command(text)
    if re.search(r"\b(minimize|minimise)\b", t):
        return True
    if re.search(r"\bhide\s+(the\s+)?(screen|window|app|this)\b", t):
        return True
    if t in ("hide", "go to tray", "make it small", "minimise", "minimize"):
        return True
    return False


def is_restore_phrase(text: str) -> bool:
    t = clean_spoken_command(text)
    return bool(
        re.search(r"\b(restore|maximize|maximise|unminimize|show window|bring back)\b", t)
        or re.search(r"^(show|restore)(\s+the)?(\s+app|\s+window)?$", t)
    )


def strip_wake(text: str) -> str:
    t = normalize(text)
    # Strip eye at start if followed by command
    if re.match(r"^eye\s+[a-z0-9]", t):
        t = re.sub(r"^eye\s+", "", t).strip()
        return clean_spoken_command(t)
    # Strip hey i
    if re.match(r"^(?:hey\s+i|ok\s+i|okay\s+i)\b", t):
        t = re.sub(r"^(?:hey\s+i|ok\s+i|okay\s+i)\s*", "", t).strip()
        return clean_spoken_command(t)
    # Strip configured aliases at start
    for alias in sorted(_wake_aliases, key=len, reverse=True):
        a = normalize(alias)
        if a and t.startswith(a + " "):
            t = t[len(a) :].strip()
            return clean_spoken_command(t)
        if a and t == a:
            return ""
    t = re.sub(rf"^{_WAKE_CLOSE}\s*", "", t).strip(" .,!?")
    return clean_spoken_command(t)


def looks_complete_command(text: str) -> bool:
    """True when a partial transcript is already a runnable command (faster than waiting for silence)."""
    t = clean_spoken_command(strip_wake(text) if is_wake_phrase(text) else text)
    if not t or len(t.split()) < 1:
        return False
    if is_close_phrase(t, session_active=True) or is_minimize_phrase(t) or is_restore_phrase(t):
        return True
    if re.match(
        r"^(click|tap|open|launch|type|write|press|scroll|copy|move|run|search|fill|wait|close|quit|exit)\b.+$",
        t,
    ):
        return True
    if re.match(r"^(again|repeat)$", t):
        return True
    return False


def classify_utterance(text: str, *, session_active: bool) -> Tuple[Kind, str]:
    raw = normalize(text)
    if not raw:
        return "ignore", ""
    if is_sleep_phrase(raw, session_active=session_active):
        return "close", ""

    woke = is_wakeup_phrase(raw)
    leftover = strip_wakeup(raw) if woke else ""
    is_wake = is_wake_phrase(raw)
    wake_cmd = clean_spoken_command(strip_wake(raw)) if is_wake else ""

    cleaned = leftover or wake_cmd or clean_spoken_command(raw)

    listening = session_active or woke or is_wake
    if listening and (is_minimize_phrase(raw) or is_minimize_phrase(cleaned)):
        return "minimize", cleaned
    if listening and (is_restore_phrase(raw) or is_restore_phrase(cleaned)):
        return "restore", cleaned
    if session_active and re.match(r"^(again|repeat|do it again|execute that|do that)$", cleaned):
        return "repeat", ""

    if woke:
        return "wake", leftover
    if is_wake:
        return "wake", wake_cmd
    if session_active:
        return "command", cleaned
    return "ignore", ""
