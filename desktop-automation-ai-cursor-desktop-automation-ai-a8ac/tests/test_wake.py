from src.speech.wake import (
    classify_utterance,
    is_close_phrase,
    is_sleep_phrase,
    is_wake_phrase,
    is_wakeup_followup,
    is_wakeup_phrase,
    looks_complete_wake,
    strip_wake,
    strip_wakeup,
)


def test_wake_variants():
    assert is_wake_phrase("DAI")
    assert is_wake_phrase("hey dai")
    assert is_wake_phrase("die")
    assert not is_wake_phrase("open chrome")
    assert not is_wake_phrase("have a nice day")
    assert is_wake_phrase("they")
    assert is_wake_phrase("day")
    assert is_wake_phrase("DAI open chrome")
    assert not is_wake_phrase("copy file they sent to desktop")


def test_wakeup_required_to_start():
    assert is_wakeup_phrase("DAI wakeup")
    assert is_wakeup_phrase("DAI wake up")
    assert is_wakeup_phrase("die wake up")
    assert is_wakeup_phrase("wake up dai")
    assert is_wakeup_phrase("hey dai wakeup")
    assert is_wakeup_phrase("day wakeup")
    assert not is_wakeup_phrase("DAI")
    assert not is_wakeup_phrase("open chrome")
    assert not is_wakeup_phrase("wake up")
    assert is_wakeup_followup("wakeup")
    assert is_wakeup_followup("wake up")
    assert not is_wakeup_followup("open chrome")


def test_sleep_phrase():
    assert is_sleep_phrase("DAI sleep")
    assert is_sleep_phrase("DAI close now")
    assert is_sleep_phrase("go to sleep", session_active=True)
    assert not is_sleep_phrase("open chrome")
    assert not is_sleep_phrase("DAI stop", session_active=True)
    assert not is_sleep_phrase("stop", session_active=True)


def test_close_phrase():
    assert is_close_phrase("DAI close now")
    assert is_close_phrase("die close now")
    assert is_close_phrase("close now", session_active=True)
    assert not is_close_phrase("close the window")
    assert not is_close_phrase("DAI stop", session_active=True)


def test_classify_session():
    kind, cmd = classify_utterance("AI", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    kind, cmd = classify_utterance("DAI", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    kind, cmd = classify_utterance("AI open chrome", session_active=False)
    assert kind == "wake"
    assert "open" in cmd and "chrome" in cmd

    kind, cmd = classify_utterance("DAI wakeup", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    kind, cmd = classify_utterance("DAI wakeup click login", session_active=False)
    assert kind == "wake"
    assert "click" in cmd and "login" in cmd

    kind, cmd = classify_utterance("click submit", session_active=True)
    assert kind == "command"
    assert cmd.startswith("click")

    kind, cmd = classify_utterance("click submit", session_active=False)
    assert kind == "ignore"

    kind, cmd = classify_utterance("AI wakeup open chrome", session_active=False)
    assert kind == "wake"
    assert "open" in cmd and "chrome" in cmd


def test_minimize_and_repeat():
    kind, _ = classify_utterance("DAI wakeup minimize the screen", session_active=False)
    assert kind == "minimize"
    kind, _ = classify_utterance("minimize", session_active=True)
    assert kind == "minimize"
    kind, _ = classify_utterance("again", session_active=True)
    assert kind == "repeat"
    kind, _ = classify_utterance("DAI sleep", session_active=True)
    assert kind == "close"


def test_clean_fillers():
    from src.speech.wake import clean_spoken_command

    assert clean_spoken_command("please open chrome") == "open chrome"
    assert "click" in clean_spoken_command("can you click login")


def test_complete_command():
    from src.speech.wake import looks_complete_command

    assert looks_complete_command("click login")
    assert looks_complete_command("open notepad")
    assert looks_complete_command("minimize the screen")
    assert not looks_complete_command("click")

    assert looks_complete_wake("ai")
    assert looks_complete_wake("dai")
    assert looks_complete_wake("ai wakeup")
    assert looks_complete_wake("AI wake up")
    assert looks_complete_wake("ai open chrome")
    assert not looks_complete_wake("open chrome")
    assert not looks_complete_wake("have a nice day")


def test_custom_agent_name_wakes():
    from src.speech.wake import agent_name, is_wakeup_phrase, sanitize_agent_name, set_agent_name

    try:
        assert sanitize_agent_name("click") == "AI"
        assert sanitize_agent_name("My Bot!") == "My Bot"
        set_agent_name("Alex")
        assert agent_name() == "Alex"
        assert is_wakeup_phrase("Alex wakeup")
        assert is_wakeup_phrase("hey alex wake up")
        assert is_wakeup_phrase("AI wakeup")
        assert not is_wakeup_phrase("open chrome")
        kind, leftover = classify_utterance("alex wakeup open chrome", session_active=False)
        assert kind == "wake"
        assert "open" in leftover and "chrome" in leftover
    finally:
        set_agent_name("AI")


def test_strip_wakeup():
    assert strip_wakeup("DAI wakeup open chrome") == "open chrome"
    assert strip_wakeup("wake up dai click login") == "click login"
    assert strip_wake("DAI click login") == "click login"
    assert strip_wake("AI open chrome") == "open chrome"
    assert strip_wake("hey AI click submit") == "click submit"
    assert strip_wake("eye open chrome") == "open chrome"


import pytest


@pytest.mark.parametrize(
    "phrase",
    [
        "AI",
        "A I",
        "A.I.",
        "a. i.",
        "ai",
        "ay eye",
        "a eye",
        "hey AI",
        "hey A I",
        "okay AI",
        "ok AI",
        "hey I",
        "eye open chrome",
        "AI open Chrome",
        "hey AI search python",
        "ok AI close tab",
        "DAI",
        "hey dai",
    ],
)
def test_all_wake_variants_trigger(phrase):
    assert is_wake_phrase(phrase), f"Expected '{phrase}' to trigger wake"


@pytest.mark.parametrize(
    "phrase",
    [
        "I think AI is cool",
        "click the AI button",
        "hi there",
        "eye",
        "the human eye",
        "apple in the eye",
        "open chrome",
        "have a nice day",
    ],
)
def test_wake_negative_cases_do_not_trigger(phrase):
    assert not is_wake_phrase(phrase), f"Expected '{phrase}' NOT to trigger wake"


def test_wake_alone_vs_wake_command():
    # Wake alone
    kind, cmd = classify_utterance("AI", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    kind, cmd = classify_utterance("hey AI", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    kind, cmd = classify_utterance("A.I.", session_active=False)
    assert kind == "wake"
    assert cmd == ""

    # Wake + command
    kind, cmd = classify_utterance("AI open Chrome", session_active=False)
    assert kind == "wake"
    assert cmd == "open chrome"

    kind, cmd = classify_utterance("hey AI click submit", session_active=False)
    assert kind == "wake"
    assert cmd == "click submit"

    kind, cmd = classify_utterance("eye open chrome", session_active=False)
    assert kind == "wake"
    assert cmd == "open chrome"


def test_emergency_stop_phrases():
    from src.nlp.engine import NLPEngine

    engine = NLPEngine()
    for phrase in [
        "stop",
        "stop now",
        "AI stop",
        "ai stop now",
        "DAI stop",
        "dai stop now",
        "cancel task",
        "emergency stop",
    ]:
        parsed = engine.parse(phrase)
        assert parsed.intent == "emergency_stop", f"Expected '{phrase}' to map to emergency_stop"

