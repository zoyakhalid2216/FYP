from src.agent.chrome_debug import list_pages
from src.agent.elements import ScreenElement
from src.agent.matcher import match_elements
from src.agent.resolver import rank_targets
from src.agent.semantic import expand_click_query
from src.agent.verify import click_succeeded, page_changed


def _login_buttons():
    return [
        ScreenElement(
            id="o",
            type="button",
            text="Login With Odoo",
            x=80,
            y=330,
            width=260,
            height=44,
            source="OCR",
        ),
        ScreenElement(
            id="m",
            type="button",
            text="login With Microsoft",
            x=80,
            y=400,
            width=280,
            height=48,
            source="OCR",
        ),
    ]


def test_semantic_phrases_all_resolve_to_microsoft_login():
    phrases = [
        "login with microsoft",
        "Login With Microsoft",
        "LOGIN WITH MICROSOFT",
        "login with Microsoft",
        "click the Microsoft login button",
        "click Microsoft",
        "sign in with Microsoft",
    ]
    els = _login_buttons()
    for phrase in phrases:
        expanded = expand_click_query(phrase)
        assert "microsoft" in expanded
        hit = match_elements(phrase, els)
        assert hit.best is not None, phrase
        assert "microsoft" in hit.best.element.text.lower(), phrase
        assert "odoo" not in hit.best.element.text.lower(), phrase
        assert hit.ambiguous is False, phrase
        ranked = rank_targets(phrase, els)
        assert ranked.element is not None, phrase
        assert "microsoft" in ranked.element.text.lower(), phrase


def test_resolver_prefers_accessibility_source():
    els = [
        ScreenElement(
            id="ocr",
            type="button",
            text="login With Microsoft",
            x=10,
            y=10,
            width=200,
            height=40,
            source="OCR",
            confidence=0.7,
        ),
        ScreenElement(
            id="a11y",
            type="button",
            text="login With Microsoft",
            x=12,
            y=12,
            width=200,
            height=40,
            source="ACCESSIBILITY",
            confidence=0.94,
        ),
    ]
    ranked = rank_targets("click microsoft", els)
    assert ranked.element is not None
    assert ranked.element.source == "ACCESSIBILITY"
    assert ranked.method == "accessibility"


def test_page_changed_on_microsoft_auth():
    before = {
        "title": "Login | Horizon",
        "url": "https://horizon.ucp.edu.pk/",
        "urls": ["https://horizon.ucp.edu.pk/"],
        "titles": ["Login | Horizon"],
    }
    after = {
        "title": "Sign in to your account",
        "url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "urls": ["https://login.microsoftonline.com/common/oauth2/v2.0/authorize"],
        "titles": ["Sign in to your account"],
    }
    assert page_changed(before, after) is True
    assert click_succeeded(before, after, frame_changed=False) is True
    assert click_succeeded(before, before, frame_changed=False) is False
    assert click_succeeded(before, before, frame_changed=True) is True


def test_chrome_debug_is_soft_fail_without_server():
    assert list_pages(port=1) == []


def test_expand_does_not_rewrite_unrelated_microsoft_phrases():
    assert expand_click_query("open microsoft word") != "login with microsoft"
    assert "word" in expand_click_query("open microsoft word")
