from src.agent.actions import intent_to_action
from src.agent.analyzer import _group_lines
from src.agent.browser import ensure_url
from src.agent.elements import ScreenElement
from src.agent.finalizer import SpeechFinalizer, looks_incomplete
from src.agent.interpreter import CommandInterpreter
from src.agent.matcher import match_elements
from src.agent.normalize import is_final_transcript, normalize_command
from src.agent.safety_gate import must_confirm
from src.agent.sensitive import history_line_for_type, is_sensitive_request, redact
from src.agent.session import CANCELLED, TaskManager
from src.vision.ocr_text import normalize_ocr_text
from src.vision.search_result import text_matches_query


def test_partial_transcript_never_becomes_an_action():
    interp = CommandInterpreter()
    result = interp.interpret("Click Login with", is_final=False)
    assert result.actions == []
    assert result.ask == "partial"
    assert is_final_transcript(is_final=False) is False
    final = interp.interpret("Click Login with Microsoft", is_final=True)
    assert final.actions
    assert final.actions[0].type == "CLICK"
    assert "microsoft" in str(final.actions[0].parameters.get("element") or "").lower()


def test_normalize_stt_mistakes():
    assert "chrome" in normalize_command("open crohm").lower()
    assert "microsoft" in normalize_command("login with micro soft").lower()


def test_go_to_domain_is_open_url():
    interp = CommandInterpreter()
    result = interp.interpret("Search horizon.ucp.edu.pk", is_final=True)
    assert result.actions
    assert result.actions[0].type == "OPEN_URL"
    assert "horizon.ucp.edu.pk" in result.actions[0].parameters.get("url", "")


def test_task_start_and_stop():
    interp = CommandInterpreter()
    start = interp.interpret("help me log into my university portal", is_final=True)
    assert start.start_task is True
    stop = interp.interpret("DAI STOP", is_final=True)
    assert stop.stop is True
    done = interp.interpret("done", is_final=True)
    assert done.end_task is True


def test_session_keeps_history_without_secrets():
    mgr = TaskManager()
    mgr.start("Log into Horizon")
    mgr.record("Opened Chrome")
    mgr.record(history_line_for_type(sensitive=True, field="password"))
    mgr.waiting_for_next()
    lines = "\n".join(mgr.session.history_lines())
    assert "Opened Chrome" in lines
    assert "password" in lines.lower()
    assert "abc123" not in lines
    assert "Waiting for next instruction" in lines


def test_interpreter_clicks_first_and_second_links():
    interp = CommandInterpreter()
    first = interp.interpret("open the first link", is_final=True)
    assert first.actions
    assert first.actions[0].type == "CLICK"
    assert first.actions[0].parameters.get("result_index") == 1
    second = interp.interpret("click the second result", is_final=True)
    assert second.actions[0].type == "CLICK"
    assert second.actions[0].parameters.get("result_index") == 2
    polite = interp.interpret("you should open the first link", is_final=True)
    assert polite.actions
    assert polite.actions[0].parameters.get("result_index") == 1


def test_element_match_ranks_microsoft_login():
    els = [
        ScreenElement(id="1", type="button", text="Login", x=10, y=10, width=80, height=30),
        ScreenElement(id="2", type="button", text="Login with Microsoft", x=10, y=80, width=220, height=40),
        ScreenElement(id="3", type="button", text="Sign in", x=10, y=140, width=80, height=30),
    ]
    hit = match_elements("Click Login with Microsoft", els)
    assert hit.best is not None
    assert "microsoft" in hit.best.element.text.lower()
    assert hit.best.score >= 0.9


def test_microsoft_button_phrase_clicks_microsoft_not_odoo():
    from src.nlp.engine import NLPEngine
    from src.vision.ocr_text import normalize_ocr_query

    parsed = NLPEngine().parse("click the login with microsoft button")
    assert parsed.intent in ("click_text", "click_button")
    assert "microsoft" in parsed.entities.get("element", "").lower()
    assert "button" not in parsed.entities.get("element", "").lower()
    assert normalize_ocr_query("login with microsoft button") == "login with microsoft"

    els = [
        ScreenElement(id="1", type="button", text="Login With Odoo", x=40, y=200, width=200, height=40),
        ScreenElement(id="2", type="button", text="login With Microsoft", x=40, y=260, width=220, height=40),
    ]
    hit = match_elements("login with microsoft button", els)
    assert hit.best is not None
    assert "microsoft" in hit.best.element.text.lower()
    assert "odoo" not in hit.best.element.text.lower()
    assert hit.best.score >= 0.9
    assert hit.ambiguous is False


def test_ambiguous_login_buttons_do_not_auto_pick():
    els = [
        ScreenElement(id="1", type="button", text="Login", x=10, y=10, width=80, height=30),
        ScreenElement(id="2", type="button", text="Admin Login", x=10, y=80, width=120, height=30),
        ScreenElement(id="3", type="button", text="Login with Microsoft", x=10, y=140, width=220, height=40),
    ]
    hit = match_elements("click the login button", els)
    assert hit.matches
    if hit.confidence >= 0.65 and len(hit.matches) > 1:
        assert hit.ambiguous or hit.best.element.text.lower() != "admin login"


def test_payment_and_sensitive_safety():
    confirm, prompt = must_confirm("click pay now")
    assert confirm is True
    assert "payment" in prompt.lower() or "proceed" in prompt.lower()
    assert is_sensitive_request("type my password")
    assert "[redacted]" in redact("password: hunter2")
    assert "hunter2" not in redact("password: hunter2")


def test_intent_mapping_and_browser_url():
    action = intent_to_action("browser_back", {}, confidence=0.9)
    assert action is not None and action.type == "BACK"
    assert ensure_url("horizon.ucp.edu.pk").startswith("https://")
    typed = intent_to_action("type_text", {"text": "hello"}, confidence=0.9)
    assert typed is not None and typed.type == "TYPE"
    scrolled = intent_to_action("scroll", {"direction": "down"}, confidence=0.9)
    assert scrolled is not None and scrolled.type == "SCROLL"


def test_speech_finalizer_holds_incomplete_then_joins():
    assert looks_incomplete("Click Login with")
    assert not looks_incomplete("Click Login with Microsoft")
    fin = SpeechFinalizer(hold_s=0.4, incomplete_s=0.6)
    assert fin.feed_final("Click Login with", now=10.0) is None
    out = fin.feed_final("Microsoft", now=10.2)
    assert out is not None
    assert "login with microsoft" in out[0].lower()


def test_speech_finalizer_timeout_releases_held_phrase():
    fin = SpeechFinalizer(hold_s=0.2, incomplete_s=0.3)
    assert fin.feed_final("Click Login with", now=1.0) is None
    assert fin.take_due(now=1.1) is None
    released = fin.take_due(now=1.5)
    assert released is not None
    assert released[0].lower().startswith("click")


def test_emergency_stop_cancels_session():
    mgr = TaskManager()
    mgr.start("portal")
    mgr.cancel("Emergency stop")
    assert mgr.session is not None
    assert mgr.session.status == CANCELLED
    assert mgr.active is False


def test_click_it_uses_last_target():
    mgr = TaskManager()
    mgr.ensure()
    mgr.session.last_target = {"text": "Next", "x": 10, "y": 20}
    hit = mgr.resolve_reference("click it")
    assert hit is not None
    assert hit.get("text") == "Next"


def test_horizon_microsoft_button_matches_despite_case_and_ocr_typos():
    assert text_matches_query("login With Microsoft", "login with microsoft")
    assert text_matches_query("Mlcrosoft", "click login with microsoft")
    assert "microsoft" in normalize_ocr_text("micro soft").lower()
    assert "microsoft" in normalize_ocr_text("Microsoit").lower()

    els = [
        ScreenElement(id="u", type="input", text="Enter Username", x=80, y=200, width=300, height=40),
        ScreenElement(id="p", type="input", text="Enter Password", x=80, y=260, width=300, height=40),
        ScreenElement(id="o", type="button", text="Login With Odoo", x=80, y=330, width=260, height=44),
        ScreenElement(id="m", type="button", text="login With Microsoft", x=80, y=400, width=280, height=48),
    ]
    hit = match_elements("Click Login with Microsoft", els)
    assert hit.best is not None
    assert "microsoft" in hit.best.element.text.lower()
    assert hit.best.score >= 0.90


def test_split_ocr_lines_still_form_microsoft_button():
    words = [
        {"x": 90, "y": 450, "w": 48, "h": 16, "label": "login", "line": 8, "block": 4, "conf": 80},
        {"x": 142, "y": 450, "w": 40, "h": 16, "label": "With", "line": 8, "block": 4, "conf": 78},
        {"x": 188, "y": 452, "w": 90, "h": 18, "label": "Microsoft", "line": 9, "block": 5, "conf": 62},
    ]
    lines = _group_lines(words)
    texts = [row["text"].lower() for row in lines]
    assert any("microsoft" in t and "login" in t for t in texts)
