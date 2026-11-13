"""SQLite connection helpers and schema bootstrap (ERD-aligned)."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import ensure_runtime_dirs, load_config, resolve_path

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_db_singleton: Optional["Database"] = None


def hash_password(password: str) -> str:
    """Store a salted password hash. Prefers bcrypt; falls back to prefixed SHA-256."""
    raw = (password or "").encode("utf-8")
    try:
        import bcrypt

        digest = bcrypt.hashpw(raw, bcrypt.gensalt(rounds=12))
        return "bcrypt$" + digest.decode("ascii")
    except Exception:
        return "sha256$" + hashlib.sha256(raw).hexdigest()


def verify_password(password: str, stored: str) -> bool:
    stored = stored or ""
    raw = (password or "").encode("utf-8")
    if stored.startswith("bcrypt$"):
        try:
            import bcrypt

            return bcrypt.checkpw(raw, stored[7:].encode("ascii"))
        except Exception:
            return False
    digest = hashlib.sha256(raw).hexdigest()
    if stored.startswith("sha256$"):
        return stored[7:] == digest
    # Legacy rows hashed with bare SHA-256
    return stored == digest


_SAMPLE_WORKFLOWS = [
    (
        "Morning Study Setup",
        "Open notes and prepare study apps",
        "voice",
        [
            (1, "open_app", "notepad", "", "", "{}"),
            (2, "wait", "", "", "1", '{"seconds":1}'),
            (3, "type_text", "notepad", "", "Morning study checklist", "{}"),
        ],
    ),
    (
        "Open Chrome & Gmail",
        "Launch browser and focus inbox workflow",
        "manual",
        [
            (1, "open_app", "chrome", "", "", "{}"),
            (2, "wait", "", "", "1", '{"seconds":1}'),
            (3, "search_web", "chrome", "", "gmail", '{"query":"gmail"}'),
        ],
    ),
    (
        "University Portal Login",
        "Open browser for portal login assist",
        "manual",
        [
            (1, "open_app", "chrome", "", "", "{}"),
            (2, "wait", "", "", "1", '{"seconds":1}'),
        ],
    ),
    (
        "Open Notepad Demo",
        "Sample multi-step workflow",
        "manual",
        [
            (1, "open_app", "notepad", "", "", "{}"),
            (2, "wait", "", "", "1", '{"seconds":1}'),
            (3, "type_text", "notepad", "", "Hello from Automate AI", "{}"),
        ],
    ),
    (
        "Open File Explorer",
        "Launch file manager",
        "manual",
        [(1, "open_app", "explorer", "", "", "{}")],
    ),
    (
        "Daily Research Setup",
        "Browser + search for research",
        "voice",
        [
            (1, "open_app", "chrome", "", "", "{}"),
            (2, "search_web", "chrome", "", "latest research papers", "{}"),
        ],
    ),
]


class Database:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        cur = self._conn.execute(sql, params)
        self._conn.commit()
        return cur

    def fetchone(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self._conn.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return list(self._conn.execute(sql, params).fetchall())

    def close(self) -> None:
        self._conn.close()

    def initialize_schema(self) -> None:
        sql = _SCHEMA_PATH.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    def seed_user_workspace(self, user_id: int, config: Optional[Dict[str, Any]] = None) -> None:
        """Create default settings + starter workflows for a real user account."""
        cfg = config or {}
        defaults = {
            "theme": cfg.get("ui", {}).get("theme", "light"),
            "dry_run": "1" if cfg.get("automation", {}).get("dry_run", False) else "0",
            "failsafe": "1" if cfg.get("automation", {}).get("failsafe", True) else "0",
            "pause_seconds": str(cfg.get("automation", {}).get("pause_seconds", 0.04)),
            "voice_sensitivity": str(cfg.get("speech", {}).get("mic_sensitivity", 0.9)),
            "mic_sensitivity": str(cfg.get("speech", {}).get("mic_sensitivity", 0.9)),
            "recognition_confidence": "0.85",
            "ai_mode": "local",
            "confirm_plan": "1",
            "min_confidence": str(cfg.get("nlp", {}).get("min_confidence", 0.45)),
            "max_actions": str(cfg.get("automation", {}).get("max_actions", 30)),
            "max_seconds": str(cfg.get("automation", {}).get("max_seconds", 60)),
            "max_retries": str(cfg.get("automation", {}).get("max_retries", 3)),
            "verify_actions": "1",
            "cloud_ai": "0",
            "store_screenshots": "1",
            "store_history": "1",
            "setup_complete": "0",
            "agent_name": str(cfg.get("speech", {}).get("wake_word") or "AI"),
            "silence_seconds": str(cfg.get("speech", {}).get("silence_seconds", 1.8)),
            "max_phrase_seconds": str(cfg.get("speech", {}).get("max_phrase_seconds", 30.0)),
            "start_timeout_seconds": str(cfg.get("speech", {}).get("start_timeout_seconds", 8.0)),
        }
        for key, value in defaults.items():
            self.execute(
                """
                INSERT INTO User_Conf (conf_key, conf_value, user_id)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, conf_key) DO UPDATE SET conf_value = excluded.conf_value
                """,
                (key, value, user_id),
            )

        existing = self.fetchone(
            "SELECT COUNT(*) AS c FROM Workflow WHERE user_id = ? AND is_active = 1",
            (user_id,),
        )
        if existing and int(existing["c"]) > 0:
            return

        for name, desc, trigger, steps in _SAMPLE_WORKFLOWS:
            wcur = self.execute(
                """
                INSERT INTO Workflow (name, description, trigger_type, is_active, user_id)
                VALUES (?, ?, ?, 1, ?)
                """,
                (name, desc, trigger, user_id),
            )
            wid = int(wcur.lastrowid)
            self.execute(
                """
                INSERT INTO AutomationRule
                    (condition, action, priority, rule_name, is_active, workflow_id)
                VALUES (?, ?, ?, ?, 1, ?)
                """,
                ('{"when":"manual"}', "run_workflow", 10, "Always run", wid),
            )
            for order, intent, app, element, value, params in steps:
                self.execute(
                    """
                    INSERT INTO Task (
                        workflow_id, step_order, intent, target_app,
                        target_element, input_value, params_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (wid, order, intent, app, element, value, params),
                )

    def seed_defaults(self, config: Dict[str, Any]) -> None:
        """Optionally create a legacy demo user (off by default)."""
        auth = config.get("auth", {})
        if not bool(auth.get("create_demo_user", False)):
            return
        username = auth.get("default_username", "demo")
        password = auth.get("default_password", "demo123")
        email = auth.get("default_email", "demo@automate.ai")
        existing = self.fetchone("SELECT user_id FROM User WHERE username = ?", (username,))
        if existing:
            return
        cur = self.execute(
            """
            INSERT INTO User (username, email, password, is_active)
            VALUES (?, ?, ?, 1)
            """,
            (username, email, hash_password(password)),
        )
        self.seed_user_workspace(int(cur.lastrowid), config)


def get_database(config: Optional[Dict[str, Any]] = None) -> Database:
    global _db_singleton
    if _db_singleton is not None:
        return _db_singleton
    cfg = config or load_config()
    ensure_runtime_dirs(cfg)
    db_path = resolve_path(cfg["paths"]["db_file"])
    # Recreate DB if schema is outdated (missing ERD columns)
    recreate = False
    if db_path.exists():
        probe = sqlite3.connect(str(db_path))
        try:
            cols = [r[1] for r in probe.execute("PRAGMA table_info(User)").fetchall()]
            if "email" not in cols or "password" not in cols:
                recreate = True
        finally:
            probe.close()
        if recreate:
            db_path.unlink(missing_ok=True)

    db = Database(db_path)
    db.initialize_schema()
    db.seed_defaults(cfg)
    _db_singleton = db
    return db


def reset_database_singleton() -> None:
    global _db_singleton
    if _db_singleton is not None:
        _db_singleton.close()
    _db_singleton = None
