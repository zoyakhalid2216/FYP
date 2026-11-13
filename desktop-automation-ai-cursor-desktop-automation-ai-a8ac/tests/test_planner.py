from src.nlp.engine import NLPEngine
from src.nlp.planner import CommandPlanner, suggest_commands


def test_planner_expands_search_and_first_result():
    nlp = NLPEngine()
    parsed = nlp.parse(
        "Open Chrome, search for today's weather, then open the first result"
    )
    plan = CommandPlanner().plan(parsed, parsed.raw_text)
    intents = [s.intent for s in plan.steps]
    assert "open_app" in intents
    assert "search_web" in intents
    assert "click_text" in intents
    assert "verify_screen" in intents
    assert plan.estimated_s > 0
    assert 0 <= plan.confidence <= 1


def test_planner_unknown_offers_suggestions():
    nlp = NLPEngine()
    parsed = nlp.parse("do the thing from yesterday please")
    plan = CommandPlanner().plan(parsed, parsed.raw_text)
    assert plan.needs_clarification
    assert plan.suggestions
    assert any("Chrome" in s or "Open" in s for s in plan.suggestions)


def test_suggest_commands_ranks_overlap():
    hits = suggest_commands("open chrome search")
    assert hits[0].lower().startswith("open chrome") or "chrome" in hits[0].lower()


def test_planner_wait_after_open():
    nlp = NLPEngine()
    parsed = nlp.parse("Open notepad")
    plan = CommandPlanner().plan(parsed)
    kinds = [s.kind for s in plan.steps]
    assert "wait" in kinds or any(s.intent == "wait" for s in plan.steps)


def test_planner_bare_click_after_search_is_first_result():
    nlp = NLPEngine()
    parsed = nlp.parse("Open Chrome and search ucp student portal and click")
    plan = CommandPlanner().plan(parsed, parsed.raw_text)
    clicks = [s for s in plan.steps if s.intent == "click_text"]
    assert clicks
    assert clicks[-1].entities.get("first_result") is True
    assert clicks[-1].entities.get("result_index") == 1


def test_planner_second_result_is_not_rewritten_to_first():
    nlp = NLPEngine()
    parsed = nlp.parse(
        "Open Chrome and search ucp student portal and click the second result"
    )
    plan = CommandPlanner().plan(parsed, parsed.raw_text)
    clicks = [s for s in plan.steps if s.intent == "click_text"]
    assert clicks
    assert clicks[-1].entities.get("result_index") == 2
    assert not clicks[-1].entities.get("first_result")
    assert not any(s.entities.get("first_result") for s in clicks)


def test_planner_close_and_minimize():
    nlp = NLPEngine()
    planner = CommandPlanner()

    for cmd, expected_intent, expected_app in [
        ("close chrome", "close_app", "chrome"),
        ("close the window", "close_app", "__focused__"),
        ("quit notepad", "close_app", "notepad"),
        ("close tab", "close_tab", None),
        ("minimize window", "minimize_window", None),
    ]:
        parsed = nlp.parse(cmd)
        plan = planner.plan(parsed, cmd)
        assert any(s.intent == expected_intent for s in plan.steps)
        if expected_app:
            step = next(s for s in plan.steps if s.intent == expected_intent)
            assert step.entities.get("app") == expected_app

