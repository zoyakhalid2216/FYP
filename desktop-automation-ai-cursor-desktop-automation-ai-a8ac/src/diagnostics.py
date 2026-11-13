"""Runtime probes for setup wizard and the Diagnostics page."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def _try(label: str, fn: Callable[[], Any]) -> Dict[str, Any]:
    try:
        detail = fn()
        return {"name": label, "ok": True, "detail": str(detail or "Ready")}
    except Exception as exc:
        return {"name": label, "ok": False, "detail": str(exc)}


def probe_all(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    cfg = config or {}
    results: List[Dict[str, Any]] = []

    results.append(_try("PyQt5", lambda: __import__("PyQt5.QtWidgets").QtWidgets.__name__))
    results.append(_try("SQLite", _probe_sqlite))
    results.append(_try("NumPy", lambda: __import__("numpy").__version__))
    results.append(_try("OpenCV", lambda: __import__("cv2").__version__))
    results.append(_try("Pillow", lambda: __import__("PIL").__version__))
    results.append(_try("PyAutoGUI", _probe_pyautogui))
    results.append(_try("Tesseract OCR", _probe_tesseract))
    results.append(_try("Screen capture", lambda: _probe_capture(cfg)))
    results.append(_try("Microphone / sounddevice", _probe_mic))
    results.append(_try("Offline speech (Vosk)", _probe_vosk))
    results.append(_try("NLP (spaCy / NLTK)", _probe_nlp))
    results.append(_try("Password hashing", _probe_crypto))
    return results


def _probe_sqlite() -> str:
    import sqlite3

    con = sqlite3.connect(":memory:")
    con.execute("SELECT 1")
    con.close()
    return "Ready"


def _probe_pyautogui() -> str:
    import pyautogui

    return f"{pyautogui.size()[0]}×{pyautogui.size()[1]}"


def _probe_tesseract() -> str:
    import pytesseract

    try:
        ver = pytesseract.get_tesseract_version()
        return f"tesseract {ver}"
    except Exception:
        # Library present; binary may be missing on PATH
        return "pytesseract imported (install Tesseract binary for live OCR)"


def _probe_capture(config: Dict[str, Any]) -> str:
    from src.vision.engine import VisionEngine

    vis = VisionEngine(config)
    frame = vis.capture_screen()
    h, w = frame.shape[:2]
    if not vis.last_capture_ok:
        raise RuntimeError(vis.last_capture_error or "capture failed")
    return f"{w}×{h}"


def _probe_mic() -> str:
    import sounddevice as sd

    n = len(sd.query_devices())
    return f"{n} PortAudio device(s)"


def _probe_vosk() -> str:
    import vosk  # noqa: F401

    return "vosk imported"


def _probe_nlp() -> str:
    bits = []
    try:
        import nltk  # noqa: F401

        bits.append("nltk")
    except Exception:
        pass
    try:
        import spacy  # noqa: F401

        bits.append("spacy")
    except Exception:
        pass
    if not bits:
        raise RuntimeError("Neither spaCy nor NLTK is importable")
    return " + ".join(bits)


def _probe_crypto() -> str:
    from src.db.database import hash_password, verify_password

    stored = hash_password("probe-secret")
    if not verify_password("probe-secret", stored):
        raise RuntimeError("hash verify failed")
    kind = "argon2/bcrypt" if stored.startswith("bcrypt$") else "sha256-fallback"
    return kind
