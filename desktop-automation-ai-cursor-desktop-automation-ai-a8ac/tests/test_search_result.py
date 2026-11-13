from src.vision.search_result import (
    FIRST_RESULT_ELEMENT,
    is_bare_click_phrase,
    is_first_result_phrase,
    list_search_results,
    parse_result_index,
    pick_first_search_result,
    pick_search_result,
    text_matches_query,
)


def test_first_result_phrases():
    assert is_first_result_phrase("click on the first result")
    assert is_first_result_phrase("open the first result")
    assert is_first_result_phrase("open the first link")
    assert is_first_result_phrase("first result")
    assert is_first_result_phrase("the first one")
    assert is_first_result_phrase(FIRST_RESULT_ELEMENT)
    assert not is_first_result_phrase("click login")


def test_second_and_third_link_phrases():
    assert parse_result_index("click on the second result") == 2
    assert parse_result_index("click the second link") == 2
    assert parse_result_index("open the second link") == 2
    assert parse_result_index("the second one") == 2
    assert parse_result_index("click result 2") == 2
    assert parse_result_index("select the third result") == 3
    assert parse_result_index("open the third result") == 3
    assert parse_result_index("pick the first link") == 1


def test_bare_click_phrases():
    assert is_bare_click_phrase("click")
    assert is_bare_click_phrase("please click")
    assert is_bare_click_phrase("click it")
    assert is_bare_click_phrase("tap that")
    assert not is_bare_click_phrase("click login")
    assert not is_bare_click_phrase("click the first result")


def test_short_ocr_words_do_not_match_long_query():
    assert text_matches_query("the", "the first result") is False
    assert text_matches_query("Login", "login") is True
    assert text_matches_query("Login With Odoo", "login with odoo") is True
    assert text_matches_query("login With Microsoft", "login with microsoft") is True
    assert text_matches_query("Microsoft", "login with microsoft") is True
    assert text_matches_query("login With Microsoft", "login with microsoft button") is True


def test_pick_first_google_result_title():
    words = [
        {"x": 40, "y": 40, "w": 80, "h": 18, "label": "Google", "line": 1, "block": 1, "conf": 90},
        {"x": 80, "y": 90, "w": 220, "h": 20, "label": "horizon.up.edu.k", "line": 2, "block": 1, "conf": 90},
        {"x": 80, "y": 210, "w": 90, "h": 16, "label": "AI", "line": 3, "block": 2, "conf": 80},
        {"x": 175, "y": 210, "w": 90, "h": 16, "label": "Overview", "line": 3, "block": 2, "conf": 80},
        {"x": 90, "y": 280, "w": 70, "h": 22, "label": "Login", "line": 4, "block": 3, "conf": 90},
        {"x": 165, "y": 280, "w": 50, "h": 22, "label": "With", "line": 4, "block": 3, "conf": 90},
        {"x": 220, "y": 280, "w": 70, "h": 22, "label": "Odoo", "line": 4, "block": 3, "conf": 90},
        {"x": 90, "y": 310, "w": 240, "h": 16, "label": "horizon.ucp.edu.pk", "line": 5, "block": 3, "conf": 88},
    ]
    hit = pick_first_search_result(words, width=1280, height=720)
    assert hit is not None
    assert "login" in hit["label"].lower()
    assert "odoo" in hit["label"].lower()


def test_live_google_second_and_third_results():
    assert parse_result_index("click on the second result") == 2
    assert parse_result_index("open the third result") == 3
    assert is_first_result_phrase("click the first result")
    words = [
        {"x": 80, "y": 40, "w": 80, "h": 16, "label": "Google", "line": 1, "block": 1, "conf": 90},
        {"x": 80, "y": 230, "w": 180, "h": 16, "label": "University of Central Punjab", "line": 2, "block": 2, "conf": 88},
        {"x": 80, "y": 252, "w": 220, "h": 14, "label": "https://horizon.ucp.edu.pk", "line": 3, "block": 2, "conf": 90},
        {"x": 80, "y": 278, "w": 70, "h": 22, "label": "Login", "line": 4, "block": 2, "conf": 90},
        {"x": 155, "y": 278, "w": 40, "h": 22, "label": "With", "line": 4, "block": 2, "conf": 90},
        {"x": 200, "y": 278, "w": 60, "h": 22, "label": "Odoo", "line": 4, "block": 2, "conf": 90},
        {"x": 80, "y": 360, "w": 140, "h": 16, "label": "Punjab Colleges", "line": 5, "block": 3, "conf": 86},
        {"x": 80, "y": 382, "w": 240, "h": 14, "label": "https://mcom.pgc.edu.pk", "line": 6, "block": 3, "conf": 88},
        {"x": 80, "y": 408, "w": 70, "h": 20, "label": "Student", "line": 7, "block": 3, "conf": 90},
        {"x": 155, "y": 408, "w": 60, "h": 20, "label": "Login", "line": 7, "block": 3, "conf": 90},
        {"x": 80, "y": 490, "w": 220, "h": 14, "label": "https://adpportal.ucp.edu.pk", "line": 8, "block": 4, "conf": 88},
        {"x": 80, "y": 516, "w": 40, "h": 20, "label": "UCP", "line": 9, "block": 4, "conf": 86},
        {"x": 130, "y": 516, "w": 80, "h": 20, "label": "Student's", "line": 9, "block": 4, "conf": 86},
        {"x": 220, "y": 516, "w": 70, "h": 20, "label": "Portal", "line": 9, "block": 4, "conf": 86},
    ]
    ranked = list_search_results(words, 1280, 720)
    assert len(ranked) >= 2
    first = pick_search_result(words, 1280, 720, 1)
    second = pick_search_result(words, 1280, 720, 2)
    assert first is not None and "odoo" in first["label"].lower()
    assert second is not None and "student" in second["label"].lower()
