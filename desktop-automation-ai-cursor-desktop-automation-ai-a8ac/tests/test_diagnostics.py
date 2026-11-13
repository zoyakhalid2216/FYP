from src.diagnostics import probe_all
from src.db.database import hash_password, verify_password


def test_probe_all_returns_named_rows():
    rows = probe_all({})
    names = [r["name"] for r in rows]
    assert "PyQt5" in names
    assert "SQLite" in names
    assert "Password hashing" in names
    assert all("ok" in r for r in rows)


def test_password_roundtrip():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    # Legacy bare sha256 still verifies
    import hashlib

    legacy = hashlib.sha256(b"legacy-pass").hexdigest()
    assert verify_password("legacy-pass", legacy)
