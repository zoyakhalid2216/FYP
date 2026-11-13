from src.nlp.clarify import clarify_heard


def test_complete_command_does_not_need_clarify():
    result = clarify_heard("Open Chrome")
    assert result.needed is False


def test_half_heard_open_asks_did_you_mean():
    result = clarify_heard("open")
    assert result.needed is True
    joined = " ".join(result.suggestions).lower()
    assert "chrome" in joined or "notepad" in joined


def test_truncated_grammar_maps_to_template():
    result = clarify_heard("open chro")
    assert result.needed is True
    assert any("chrome" in s.lower() for s in result.suggestions)


def test_click_stub_and_google_alternatives():
    result = clarify_heard("click log", alternatives=["click login", "click lock"])
    assert result.needed is True
    joined = " ".join(result.suggestions).lower()
    assert "login" in joined


def test_unknown_garbage_still_offers_heard():
    result = clarify_heard("asdf qwer zxcv")
    assert result.needed is True
    assert result.suggestions
