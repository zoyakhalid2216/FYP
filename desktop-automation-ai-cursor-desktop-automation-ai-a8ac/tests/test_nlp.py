from src.nlp.engine import NLPEngine


def test_open_app_and_search():
    engine = NLPEngine()
    parsed = engine.parse("Open Chrome and search weather")
    assert parsed.intent == "open_app"
    assert parsed.entities.get("app") == "chrome"
    assert len(parsed.steps) >= 2
    assert parsed.steps[1]["intent"] == "search_web"


def test_click_and_type():
    engine = NLPEngine()
    click = engine.parse("Click Login")
    assert click.intent == "click_text"
    assert "login" in click.entities.get("element", "").lower()

    typed = engine.parse('Type "hello world"')
    assert typed.intent == "type_text"
    assert "hello" in typed.entities.get("text", "").lower()


def test_wait_scroll_workflow():
    engine = NLPEngine()
    assert engine.parse("wait 2 seconds").intent == "wait"
    assert engine.parse("scroll down 5").entities.get("amount") == 5
    assert engine.parse("run workflow Open Notepad Demo").intent == "run_workflow"
    short = engine.parse("Run Morning Study Setup")
    assert short.intent == "run_workflow"
    assert "morning" in short.entities.get("workflow", "").lower()


def test_copy_and_move_file():
    engine = NLPEngine()
    copy = engine.parse("Copy file report to Desktop")
    assert copy.intent == "copy_file"
    assert "report" in copy.entities.get("source", "").lower()
    assert "desktop" in copy.entities.get("destination", "").lower()

    paste = engine.parse("Copy file phase2 doc and paste it to Documents")
    assert paste.intent == "copy_file"
    assert "phase2" in paste.entities.get("source", "").lower()
    assert "document" in paste.entities.get("destination", "").lower()

    move = engine.parse("Move file notes.txt to Downloads")
    assert move.intent == "move_file"
    assert "notes" in move.entities.get("source", "").lower()
    assert "download" in move.entities.get("destination", "").lower()


def test_click_button_and_fill_form():
    engine = NLPEngine()
    click = engine.parse("Click button Login")
    assert click.intent == "click_button"
    assert "login" in click.entities.get("element", "").lower()

    filled = engine.parse("Fill username with alice")
    assert filled.intent == "fill_form"
    assert "username" in filled.entities.get("field", "").lower()
    assert "alice" in filled.entities.get("text", "").lower()


def test_multi_step_then_and_first_result():
    engine = NLPEngine()
    parsed = engine.parse(
        "Open Chrome, search for FYP ideas, then open the first result"
    )
    intents = [s["intent"] for s in parsed.steps]
    assert "open_app" in intents
    assert "search_web" in intents
    assert "click_text" in intents


def test_unknown_command_graceful():
    engine = NLPEngine()
    parsed = engine.parse("asdf qwer zxcv")
    assert parsed.intent == "unknown"
    assert parsed.confidence < 0.5


def test_open_file_and_folder():
    engine = NLPEngine()
    f = engine.parse("Open file phase2 doc")
    assert f.intent == "open_file"
    assert "phase2" in f.entities.get("query", "").lower()

    folder = engine.parse("Open folder Downloads")
    assert folder.intent == "open_file"
    assert "download" in folder.entities.get("query", "").lower()


def test_open_chrome_still_app():
    engine = NLPEngine()
    parsed = engine.parse("Open chrome")
    assert parsed.intent == "open_app"
    assert parsed.entities.get("app") == "chrome"


def test_spacy_nltk_tokenization():
    """NLP engine must produce tokens/lemmas via spaCy and/or NLTK."""
    engine = NLPEngine()
    parsed = engine.parse("Open notepad")
    assert parsed.tokens
    assert parsed.lemmas
    assert parsed.intent == "open_app"
    assert parsed.entities.get("app") == "notepad"


def test_minimize_restore_and_spoken_fillers():
    engine = NLPEngine()
    assert engine.parse("minimize the screen").intent == "minimize_window"
    assert engine.parse("please click login").intent == "click_text"
    spoken = engine.parse("say hello world")
    assert spoken.intent == "type_text"
    assert "hello" in spoken.entities.get("text", "").lower()
    assert engine.parse("restore the window").intent == "restore_window"


def test_ambiguous_and_malformed():
    engine = NLPEngine()
    empty = engine.parse("   ")
    assert empty.intent == "unknown"
    weird = engine.parse("!!! ???")
    assert weird.intent == "unknown"
    first = engine.parse("open the first result")
    assert first.intent == "click_text"
    assert first.entities.get("element") == "__first_result__"

    spoken = engine.parse("click on the first result")
    assert spoken.intent == "click_text"
    assert spoken.entities.get("element") == "__first_result__"
    assert spoken.entities.get("first_result") is True

    second = engine.parse("click on the second result")
    assert second.intent == "click_text"
    assert second.entities.get("result_index") == 2

    nav = engine.parse("go to horizon.ucp.edu.pk")
    assert nav.intent == "open_url"
    assert "horizon" in str(nav.entities.get("url") or "")

    assert engine.parse("go back").intent == "browser_back"
    assert engine.parse("new tab").intent == "new_tab"
    assert engine.parse("close this tab").intent == "close_tab"

    little = engine.parse("scroll a little down")
    assert little.intent == "scroll"
    assert little.entities.get("direction") == "down"
    assert little.entities.get("amount") == 2

    click_help = engine.parse("help me click the email field")
    assert click_help.intent == "click_text"

    first_link = engine.parse("open the first link")
    assert first_link.intent == "click_text"
    assert first_link.entities.get("result_index") == 1
    assert first_link.entities.get("first_result") is True

    second_link = engine.parse("click on the second link")
    assert second_link.intent == "click_text"
    assert second_link.entities.get("result_index") == 2

    the_one = engine.parse("the first one")
    assert the_one.intent == "click_text"
    assert the_one.entities.get("result_index") == 1

    result_two = engine.parse("click result 2")
    assert result_two.intent == "click_text"
    assert result_two.entities.get("result_index") == 2


def test_search_and_bare_click_is_first_result():
    engine = NLPEngine()
    parsed = engine.parse("open chrome and search ucp student portal and click")
    clicks = [s for s in (parsed.steps or []) if s.get("intent") == "click_text"]
    assert clicks
    last = clicks[-1]
    assert last["entities"].get("first_result") is True
    assert last["entities"].get("result_index") == 1
    assert last["entities"].get("element") == "__first_result__"

    spoken = engine.parse("search weather then click")
    click = [s for s in spoken.steps if s.get("intent") == "click_text"][-1]
    assert click["entities"].get("first_result") is True


def test_close_and_minimize_phrases_issue4():
    engine = NLPEngine()

    # close chrome
    p1 = engine.parse("close chrome")
    assert p1.intent == "close_app"
    assert p1.entities.get("app") == "chrome"

    # close the window
    p2 = engine.parse("close the window")
    assert p2.intent == "close_app"
    assert p2.entities.get("app") in ("__focused__", "the window")

    # close this window
    p3 = engine.parse("close this window")
    assert p3.intent == "close_app"
    assert p3.entities.get("app") in ("__focused__", "this window")

    # quit notepad
    p4 = engine.parse("quit notepad")
    assert p4.intent == "close_app"
    assert p4.entities.get("app") == "notepad"

    # exit chrome
    p5 = engine.parse("exit chrome")
    assert p5.intent == "close_app"
    assert p5.entities.get("app") == "chrome"

    # shut down notepad
    p6 = engine.parse("shut down notepad")
    assert p6.intent == "close_app"
    assert p6.entities.get("app") == "notepad"

    # close tab
    p7 = engine.parse("close tab")
    assert p7.intent == "close_tab"

    # close this tab
    p8 = engine.parse("close this tab")
    assert p8.intent == "close_tab"

    # minimize window
    p9 = engine.parse("minimize window")
    assert p9.intent == "minimize_window"


