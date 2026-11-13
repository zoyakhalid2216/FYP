"""NLP Engine: fast rule path + optional spaCy/NLTK enrichment."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from src.speech.wake import clean_spoken_command
from src.vision.search_result import (
    first_result_entities,
    is_bare_click_phrase,
    parse_result_index,
    ranked_result_entities,
)

# Shared lazy handles so the app doesn't reload models repeatedly
_SPACY_NLP = None
_SPACY_TRIED = False
_NLTK_READY = False
_NLTK_TRIED = False


@dataclass
class ParsedCommand:
    raw_text: str
    intent: str
    entities: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    tokens: List[str] = field(default_factory=list)
    lemmas: List[str] = field(default_factory=list)
    pos_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "google": "google",
    "browser": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "notepad": "notepad",
    "calculator": "calculator",
    "calc": "calculator",
    "terminal": "terminal",
    "cmd": "cmd",
    "explorer": "explorer",
    "file explorer": "explorer",
    "vscode": "code",
    "vs code": "code",
    "code": "code",
    "gmail": "gmail",
    "youtube": "youtube",
}


def _fill_empty_clicks_after_search(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Bare 'click' after a Google search means the first result."""
    out: List[Dict[str, Any]] = []
    seen_search = False
    for step in steps:
        intent = str(step.get("intent") or "")
        entities = dict(step.get("entities") or {})
        if intent == "search_web":
            seen_search = True
        if intent in ("click_text", "click_button"):
            element = str(entities.get("element") or "").strip()
            if not element:
                if seen_search and not entities.get("first_result"):
                    entities.update(first_result_entities())
                    step = {
                        **step,
                        "intent": "click_text",
                        "entities": entities,
                        "confidence": max(float(step.get("confidence") or 0), 0.9),
                    }
                    seen_search = False
                else:
                    continue
            else:
                seen_search = False
        out.append(step)
    return out


class NLPEngine:
    """Intent classification & entity extraction (fast-first, spaCy/NLTK optional)."""

    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        lazy: bool = True,
        min_confidence: float = 0.45,
    ) -> None:
        self._spacy_model = spacy_model
        self._lazy = lazy
        self.min_confidence = float(min_confidence)
        if not lazy:
            self._ensure_spacy()
            self._ensure_nltk()

    def _ensure_spacy(self):
        global _SPACY_NLP, _SPACY_TRIED
        if _SPACY_TRIED:
            return _SPACY_NLP
        _SPACY_TRIED = True
        try:
            import spacy

            try:
                _SPACY_NLP = spacy.load(self._spacy_model)
            except OSError:
                _SPACY_NLP = spacy.blank("en")
        except Exception:
            _SPACY_NLP = None
        return _SPACY_NLP

    def _ensure_nltk(self) -> bool:
        global _NLTK_READY, _NLTK_TRIED
        if _NLTK_TRIED:
            return _NLTK_READY
        _NLTK_TRIED = True
        try:
            import nltk

            for pkg in ("punkt", "punkt_tab"):
                try:
                    nltk.data.find(f"tokenizers/{pkg}")
                except LookupError:
                    nltk.download(pkg, quiet=True)
            _NLTK_READY = True
        except Exception:
            _NLTK_READY = False
        return _NLTK_READY

    def tokenize(self, text: str) -> List[str]:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return []
        # Fast path — avoid model load for common commands
        return re.findall(r"[A-Za-z0-9_']+|[^\s\w]", cleaned)

    def analyze(self, text: str, *, enrich: bool = False) -> Dict[str, Any]:
        cleaned = " ".join(text.strip().split())
        tokens = self.tokenize(cleaned)
        lemmas = [t.lower() for t in tokens]
        pos_tags: List[str] = []
        noun_chunks: List[str] = []
        spacy_ents: List[Dict[str, str]] = []

        if enrich:
            nlp = self._ensure_spacy()
            if nlp is not None and cleaned:
                doc = nlp(cleaned)
                tokens = [t.text for t in doc] or tokens
                if any(getattr(t, "pos_", "") for t in doc):
                    lemmas = [t.lemma_.lower() for t in doc]
                    pos_tags = [t.pos_ for t in doc]
                try:
                    noun_chunks = [c.text for c in doc.noun_chunks]
                except Exception:
                    noun_chunks = []
                spacy_ents = [
                    {"text": e.text, "label": e.label_} for e in getattr(doc, "ents", [])
                ]
            elif self._ensure_nltk() and cleaned:
                from nltk.tokenize import word_tokenize

                tokens = word_tokenize(cleaned)
                lemmas = [t.lower() for t in tokens]

        return {
            "tokens": tokens,
            "lemmas": lemmas or [t.lower() for t in tokens],
            "pos_tags": pos_tags,
            "noun_chunks": noun_chunks,
            "spacy_ents": spacy_ents,
        }

    def parse(self, text: str) -> ParsedCommand:
        raw = clean_spoken_command(text)
        raw = " ".join(raw.split())
        if not raw:
            return ParsedCommand(raw_text=text, intent="unknown", confidence=0.0)

        # Keep copy/move "… and paste … to …" as one command (do not split on "and")
        copy_paste = bool(
            re.search(
                r"\b(copy|move|paste)\b.+\b(to|into|in)\b",
                raw,
                flags=re.I,
            )
            or re.search(r"\bcopy\b.+\band\s+paste\b", raw, flags=re.I)
        )

        # Split on "then" / "and then" / "and" when they join commands (not quoted / copy-paste)
        then_split = bool(
            not copy_paste
            and re.search(r"\b(?:and\s+then|then)\b", raw, flags=re.I)
            and not re.search(r"[\"'].*\bthen\b.*[\"']", raw, flags=re.I)
        )
        and_split = bool(
            not copy_paste
            and not then_split
            and re.search(r"\band\b", raw, flags=re.I)
            and not re.search(r"[\"'].*\band\b.*[\"']", raw, flags=re.I)
        )
        if then_split or and_split:
            parts = re.split(
                r"\s*(?:,\s*)?(?:and\s+then|then|, and|and)\s+",
                raw,
                flags=re.I,
            ) if then_split else re.split(r"\band\b", raw, flags=re.I)
            extra: List[str] = []
            for part in parts:
                extra.extend(
                    re.split(
                        r"\s*,\s*(?=(?:open|launch|search|google|click|tap|type|"
                        r"wait|run|press|scroll|copy|move|fill|write)\b)",
                        part,
                        flags=re.I,
                    )
                )
            parts = extra
            steps: List[Dict[str, Any]] = []
            confidences: List[float] = []
            for part in parts:
                part = part.strip(" ,.")
                if not part:
                    continue
                parsed = self._parse_single(part)
                intent = parsed.intent
                entities = dict(parsed.entities or {})
                confidence = parsed.confidence
                # "search X and click" — leftover "click" is unknown until we see search_web
                if intent == "unknown" and is_bare_click_phrase(part):
                    intent = "click_text"
                    entities = {"element": ""}
                    confidence = 0.72
                steps.append(
                    {
                        "intent": intent,
                        "entities": entities,
                        "confidence": confidence,
                    }
                )
                confidences.append(confidence)
            steps = _fill_empty_clicks_after_search(steps)
            primary = steps[0] if steps else {"intent": "unknown", "entities": {}, "confidence": 0.0}
            analysis = self.analyze(raw, enrich=False)
            return ParsedCommand(
                raw_text=raw,
                intent=primary["intent"],
                entities=primary.get("entities", {}),
                confidence=sum(confidences) / len(confidences) if confidences else 0.0,
                steps=steps,
                tokens=analysis["tokens"],
                lemmas=analysis["lemmas"],
                pos_tags=analysis["pos_tags"],
            )

        single = self._parse_single(raw)
        single.steps = [
            {
                "intent": single.intent,
                "entities": single.entities,
                "confidence": single.confidence,
            }
        ]
        return single

    def _parse_single(self, text: str) -> ParsedCommand:
        analysis = self.analyze(text, enrich=False)
        lemmas = analysis["lemmas"]
        tokens = analysis["tokens"]
        lower = text.lower().strip()

        intent, confidence = self._classify_intent(lemmas, lower)
        entities = self._extract_entities(intent, text, analysis)

        # Light enrichment only when entity extraction looks weak
        if intent == "unknown" or (intent == "open_app" and not entities.get("app")):
            analysis = self.analyze(text, enrich=True)
            lemmas = analysis["lemmas"] or lemmas
            intent, confidence = self._classify_intent(lemmas, lower)
            entities = self._extract_entities(intent, text, analysis)

        if confidence < self.min_confidence and intent != "unknown":
            # Keep intent but flag low confidence for UI messaging
            entities["low_confidence"] = True

        if intent in ("open_app",) and not entities.get("app") and not entities.get("path"):
            intent, confidence = "unknown", 0.15
        if intent == "open_file" and not (entities.get("query") or entities.get("path")):
            intent, confidence = "unknown", 0.15
        if intent in ("click_text", "click_button") and not entities.get("element"):
            intent, confidence = "unknown", 0.15
        if intent == "fill_form" and not (entities.get("field") or entities.get("text")):
            intent, confidence = "unknown", 0.15
        if intent == "type_text" and not entities.get("text"):
            intent, confidence = "unknown", 0.15
        if intent == "search_web" and not entities.get("query"):
            intent, confidence = "unknown", 0.15
        if intent in ("copy_file", "move_file") and not (
            entities.get("source") and entities.get("destination")
        ):
            intent, confidence = "unknown", 0.15
        if intent == "run_workflow" and not entities.get("workflow"):
            intent, confidence = "unknown", 0.15

        return ParsedCommand(
            raw_text=text,
            intent=intent,
            entities=entities,
            confidence=confidence,
            tokens=tokens,
            lemmas=lemmas,
            pos_tags=analysis.get("pos_tags") or [],
        )

    def _classify_intent(self, lemmas: List[str], lower: str) -> Tuple[str, float]:
        # Copy / move / paste file (before generic "and" / open handling)
        if re.search(
            r"\b(copy|move|paste)\b.+\b(to|into|in)\b",
            lower,
        ) or re.search(r"\bcopy\b.+\band\s+paste\b", lower):
            if "move" in lemmas and "copy" not in lemmas and "paste" not in lemmas:
                return "move_file", 0.94
            return "copy_file", 0.94

        if re.search(r"\b(run|replay|execute)\s+(workflow|macro)\b", lower):
            return "run_workflow", 0.95
        # "run Morning Study Setup" / "execute Open Notepad Demo"
        m_run = re.search(r"\b(run|replay|execute)\s+(.+)$", lower)
        if m_run:
            name = m_run.group(2).strip()
            first = name.split()[0] if name else ""
            blocked = {
                "chrome",
                "notepad",
                "calculator",
                "calc",
                "firefox",
                "edge",
                "diagnostics",
                "system",
                "command",
                "test",
            }
            if name and first not in blocked and first not in _APP_ALIASES:
                return "run_workflow", 0.9

        if re.search(
            r"\bpress\s+(key\s+)?(enter|tab|escape|esc|space|backspace|ctrl\+|alt\+|cmd\+|win\+)",
            lower,
        ):
            return "press_key", 0.9
        if "scroll" in lemmas or lower.startswith("scroll"):
            return "scroll", 0.9
        if re.search(r"\b(minimize|minimise)\b", lower) or re.search(
            r"\bhide\s+(the\s+)?(screen|window|app)\b", lower
        ):
            return "minimize_window", 0.96
        if re.search(r"\b(restore|maximize|maximise|unminimize)\b", lower):
            return "restore_window", 0.95
        if any(w in lemmas for w in ("wait", "pause", "sleep")):
            return "wait", 0.93
        if re.search(r"\b((dai|ai)\s+)?stop(\s+now)?\b|^cancel( task)?$", lower):
            return "emergency_stop", 0.99
        if re.search(r"^(done|finish(ed)?|end task|that'?s all)$", lower):
            return "end_task", 0.96
        if re.search(
            r"\b(help me|log me in|walk me through|start (a |the )?task)\b", lower
        ) and not re.search(r"\b(click|type|open chrome|go to)\b", lower):
            return "start_task", 0.9
        if re.search(r"\b(log into|login to)\s+(my|the)\b", lower) and not re.search(
            r"\b(click|type|open chrome)\b", lower
        ):
            return "start_task", 0.88
        if re.search(r"\b(go back|back( a page)?)\b", lower) and "click" not in lower:
            return "browser_back", 0.93
        if re.search(r"\b(go forward|forward)\b", lower) and "click" not in lower:
            return "browser_forward", 0.9
        if re.search(r"\b(refresh|reload)\b", lower):
            return "browser_refresh", 0.92
        if re.search(r"\b(new tab|open (a )?tab)\b", lower):
            return "new_tab", 0.93
        if re.search(r"\b(close\s+(?:this\s+|the\s+|current\s+)?tab)\b", lower):
            return "close_tab", 0.93
        if re.search(r"\b(switch|next|previous)\s+tab\b", lower):
            return "switch_tab", 0.9
        if (
            re.search(r"\b(?:close|quit|exit|shut\s+down)\s+(?:the\s+|this\s+|current\s+)?(?:window|screen|app)\b", lower)
            or lower in ("close window", "close the window", "close this window", "exit window", "quit window")
        ):
            return "close_app", 0.95
        if re.search(r"\b(?:close|quit|exit|shut\s+down)\s+(.+)$", lower):
            m_cand = re.search(r"\b(?:close|quit|exit|shut\s+down)\s+(.+)$", lower)
            cand = m_cand.group(1).strip() if m_cand else ""
            first_c = cand.split()[0] if cand else ""
            if cand in _APP_ALIASES or first_c in _APP_ALIASES or any(k in lower for k in ("chrome", "notepad", "edge", "firefox", "word", "excel", "calc", "calculator", "terminal", "cmd", "code", "vscode", "explorer")):
                return "close_app", 0.93
        if re.search(r"\bplay\s+(music|a song|songs)\b", lower):
            return "open_url", 0.86
        if re.search(r"\b(go to|visit|navigate to)\s+\S+", lower):
            return "open_url", 0.92
        if parse_result_index(lower) and re.search(
            r"\b(click|tap|open|select|choose|pick|result|link|hit|"
            r"first|second|third|fourth|fifth|1st|2nd|3rd)\b",
            lower,
        ):
            return "click_text", 0.95
        # Open file / folder / document before generic open_app
        if re.search(
            r"\b(open|launch|show|start)\s+(?:(?:the|my|a|an)\s+)?"
            r"(file|document|folder|directory|pdf|docx?|xlsx?|pptx?|txt|zip)\b",
            lower,
        ) or re.search(
            r"\b(open|launch|show)\s+.+\.(pdf|docx?|xlsx?|pptx?|txt|png|jpg|jpeg|csv|zip|mp4|mp3)\b",
            lower,
        ) or re.search(r"\b(open|show)\s+folder\b", lower):
            return "open_file", 0.94
        if any(w in lemmas for w in ("open", "launch", "start", "show")):
            # If target looks like a known app → open_app; else may still be a file name
            m = re.search(r"\b(?:open|launch|start|show)\s+(.+)$", lower)
            target = (m.group(1) if m else "").strip()
            target = re.split(r"\band\b", target, maxsplit=1)[0].strip()
            key = target.lower()
            first = key.split()[0] if key else ""
            if key in _APP_ALIASES or first in _APP_ALIASES:
                return "open_app", 0.92
            # Prefer file search for free-form names ("open phase2 doc")
            if key and first not in ("chrome", "notepad", "calculator", "terminal", "cmd"):
                return "open_file", 0.86
            return "open_app", 0.9
        if "search" in lemmas or re.search(r"^\s*google\s+\S+", lower):
            return "search_web", 0.9
        # SDS intents: click_button / fill_form (plus click_text alias)
        if re.search(r"\b(click|tap)\s+(?:on\s+)?(?:the\s+)?button\b", lower):
            return "click_button", 0.93
        if re.search(
            r"\b(fill|complete)\s+(?:(?:the|a)\s+)?form\b",
            lower,
        ) or re.search(
            r"\bfill\s+(?:(?:in|into|the)\s+)?(?P<field>.+?)\s+with\b",
            lower,
        ):
            return "fill_form", 0.92
        if any(w in lemmas for w in ("click", "tap")):
            return "click_text", 0.88
        if any(w in lemmas for w in ("type", "write", "fill", "say", "dictate")) or (
            "enter" in lemmas and not re.search(r"\bpress\s+enter\b", lower)
        ):
            return "type_text", 0.86
        return "unknown", 0.2

    def _extract_entities(
        self, intent: str, text: str, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}
        if intent == "open_file":
            m = re.search(
                r"\b(?:open|launch|show|start)\s+(?:(?:the|my|a|an)\s+)?"
                r"(?:file|document|folder|directory)?\s*[\"']?(?P<q>.+?)[\"']?\s*$",
                text,
                re.I,
            )
            query = (m.group("q") if m else "").strip(" \"'")
            query = re.split(r"\band\b", query, maxsplit=1, flags=re.I)[0].strip()
            # Strip leading type words if still present
            query = re.sub(
                r"^(file|document|folder|directory)\s+", "", query, flags=re.I
            ).strip()
            entities["query"] = query
            entities["kind"] = "folder" if re.search(r"\bfolder|directory\b", text, re.I) else "file"
            # Direct path / extension hint
            path_m = re.search(
                r"([A-Za-z]:\\[^\"]+|/[^\"]+|\S+\.(?:pdf|docx?|xlsx?|pptx?|txt|png|jpg|jpeg|csv|zip))",
                text,
                re.I,
            )
            if path_m:
                entities["path"] = path_m.group(1)
        elif intent == "open_app":
            m = re.search(r"\b(?:open|launch|start|show)\s+(.+)$", text, re.I)
            app = (m.group(1) if m else "").strip()
            # Strip trailing follow-ups already split; keep first app token phrase
            app = re.split(r"\band\b", app, maxsplit=1, flags=re.I)[0].strip()
            for chunk in analysis.get("noun_chunks") or []:
                cleaned = re.sub(
                    r"^(open|launch|start|show)\s+", "", chunk.strip(), flags=re.I
                ).strip()
                key = cleaned.lower()
                if key in _APP_ALIASES or key.split()[0] in _APP_ALIASES:
                    app = cleaned
                    break
            app_key = app.lower().strip()
            if app_key in _APP_ALIASES:
                entities["app"] = _APP_ALIASES[app_key]
            elif app_key:
                first = app_key.split()[0]
                entities["app"] = _APP_ALIASES.get(first, first)
            else:
                entities["app"] = ""
            # Keep raw for fallback file search
            entities["query"] = app
        elif intent in ("click_text", "click_button"):
            m = re.search(
                r"\b(?:click|tap|open|select|choose|pick|press)\s+"
                r"(?:on\s+)?(?:the\s+)?(?:button\s+)?(.+)$",
                text,
                re.I,
            )
            element = (m.group(1) if m else "").strip(" \"'")
            element = re.sub(r"^(?:on\s+)?(?:the\s+)?", "", element, flags=re.I).strip()
            element = re.sub(r"\s+(buttons?|btn|links?|icons?)$", "", element, flags=re.I).strip()
            idx = parse_result_index(text) or parse_result_index(element)
            if idx:
                entities.update(ranked_result_entities(idx))
            else:
                entities["element"] = element
            if intent == "click_button":
                entities["element_type"] = "button"
        elif intent == "fill_form":
            m = re.search(
                r"\bfill\s+(?:(?:in|into|the)\s+)?(?P<field>.+?)\s+with\s+[\"']?(?P<text>.+?)[\"']?\s*$",
                text,
                re.I,
            )
            if m:
                entities["field"] = m.group("field").strip(" \"'")
                entities["text"] = (m.group("text") or "").strip(" \"'")
            else:
                m2 = re.search(
                    r"\b(?:fill|complete)\s+(?:(?:the|a)\s+)?form\s+(?:with\s+)?[\"']?(?P<text>.+?)[\"']?\s*$",
                    text,
                    re.I,
                )
                entities["field"] = ""
                entities["text"] = (m2.group("text") if m2 else "").strip(" \"'")
        elif intent == "type_text":
            m = re.search(
                r"\b(?:type|enter|write|fill|say|dictate)\s+(?:(?:in|into|the)\s+(?P<field>.+?)\s+with\s+)?[\"']?(?P<text>.+?)[\"']?\s*$",
                text,
                re.I,
            )
            if m:
                if m.groupdict().get("field"):
                    entities["field"] = m.group("field").strip()
                entities["text"] = (m.group("text") or "").strip(" \"'")
            else:
                entities["text"] = ""
        elif intent == "search_web":
            m = re.search(r"\b(?:search(?:\s+for)?|google)\s+(.+)$", text, re.I)
            entities["query"] = (m.group(1) if m else "").strip(" \"'")
        elif intent == "open_url":
            m = re.search(
                r"\b(?:go to|visit|navigate to|open|search)\s+(?:https?://)?(?P<url>\S+)",
                text,
                re.I,
            )
            url = (m.group("url") if m else "").strip(" \"'")
            if re.search(r"\bplay\s+(music|a song|songs)\b", text, re.I):
                url = "https://music.youtube.com"
            entities["url"] = url
            entities["query"] = url
        elif intent == "switch_tab":
            entities["which"] = "previous" if re.search(r"\bprev|previous\b", text, re.I) else "next"
        elif intent == "start_task":
            entities["goal"] = text
        elif intent == "close_app":
            m = re.search(r"\b(?:close|quit|exit|shut\s+down)\s+(.+)$", text, re.I)
            raw_target = (m.group(1) if m else "").strip(" \"'.,!?")
            low = raw_target.lower()
            if low in ("the window", "this window", "window", "current window", "the app", "this app", "the screen", "this screen"):
                entities["app"] = "__focused__"
                entities["target"] = "window"
            elif low in _APP_ALIASES:
                entities["app"] = _APP_ALIASES[low]
            else:
                first = low.split()[0] if low else ""
                entities["app"] = _APP_ALIASES.get(first, low)
        elif intent == "minimize_window":
            m = re.search(r"\b(?:minimize|minimise|hide)\s+(.+)$", text, re.I)
            if m:
                raw_target = m.group(1).strip(" \"'.,!?").lower()
                if raw_target in ("the window", "this window", "window", "the screen", "screen", "the app", "app"):
                    entities["app"] = "__focused__"
                elif raw_target in _APP_ALIASES:
                    entities["app"] = _APP_ALIASES[raw_target]
                else:
                    first = raw_target.split()[0] if raw_target else ""
                    entities["app"] = _APP_ALIASES.get(first, raw_target)
        elif intent == "press_key":
            m = re.search(
                r"\b(?:press|hit)\s+(?:key\s+)?(?P<key>enter|tab|escape|esc|space|backspace|ctrl\+[a-z]|alt\+[a-z]|cmd\+[a-z]|win\+[a-z])\b",
                text,
                re.I,
            )
            key = (m.group("key") if m else "enter").lower().replace("esc", "escape")
            entities["key"] = key
        elif intent == "scroll":
            m = re.search(
                r"\bscroll\s+(?:a\s+little\s+)?(?P<direction>up|down|left|right)"
                r"(?:\s+a\s+little)?(?:\s+(?P<amount>\d+))?",
                text,
                re.I,
            )
            entities["direction"] = (m.group("direction") if m else "down").lower()
            if m and m.group("amount"):
                entities["amount"] = int(m.group("amount"))
            elif re.search(r"\ba\s+little\b", text, re.I):
                entities["amount"] = 2
            else:
                entities["amount"] = 3
        elif intent == "wait":
            m = re.search(r"(?P<seconds>\d+(?:\.\d+)?)", text)
            entities["seconds"] = float(m.group("seconds")) if m else 1.0
        elif intent == "run_workflow":
            m = re.search(
                r"\b(?:run|replay|execute)\s+(?:workflow|macro)\s+(.+)$",
                text,
                re.I,
            )
            if not m:
                m = re.search(r"\b(?:run|replay|execute)\s+(.+)$", text, re.I)
            name = (m.group(1) if m else "").strip(" \"'")
            name = re.sub(r"^(workflow|macro)\s+", "", name, flags=re.I).strip()
            entities["workflow"] = name
        elif intent in ("copy_file", "move_file"):
            src, dst = self._parse_copy_move(text)
            entities["source"] = src
            entities["destination"] = dst
        if analysis.get("spacy_ents"):
            entities["ner"] = analysis["spacy_ents"]
        return entities

    def _parse_copy_move(self, text: str) -> Tuple[str, str]:
        """Extract source and destination from copy/move/paste phrases."""
        patterns = [
            # copy file X and paste it to Y
            r"\b(?:copy|paste)\s+(?:(?:the|a|an|my)\s+)?(?:file|folder|document)?\s*"
            r"[\"']?(?P<source>.+?)[\"']?\s+and\s+paste(?:\s+it)?\s+(?:to|into|in)\s+"
            r"[\"']?(?P<dest>.+?)[\"']?\s*$",
            # copy file X to Y / move file X to Y / paste file X to Y
            r"\b(?:copy|move|paste)\s+(?:(?:the|a|an|my)\s+)?(?:file|folder|document)?\s*"
            r"[\"']?(?P<source>.+?)[\"']?\s+(?:to|into|in)\s+"
            r"[\"']?(?P<dest>.+?)[\"']?\s*$",
            # copy X to Y (no file keyword)
            r"\b(?:copy|move|paste)\s+[\"']?(?P<source>.+?)[\"']?\s+(?:to|into|in)\s+"
            r"[\"']?(?P<dest>.+?)[\"']?\s*$",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.I)
            if m:
                src = m.group("source").strip(" \"'")
                dst = m.group("dest").strip(" \"'")
                src = re.sub(r"^(file|folder|document)\s+", "", src, flags=re.I).strip()
                dst = re.sub(r"^(file|folder|document|the|my)\s+", "", dst, flags=re.I).strip()
                # Drop trailing "it" from awkward speech
                src = re.sub(r"\s+it$", "", src, flags=re.I).strip()
                return src, dst
        return "", ""
