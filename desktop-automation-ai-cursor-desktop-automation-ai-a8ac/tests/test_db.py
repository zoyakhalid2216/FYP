from pathlib import Path

from src.config import load_config
from src.db.database import Database, reset_database_singleton
from src.db.repositories import (
    ExecutionLogRepository,
    NLPCommandRepository,
    ScreenCaptureRepository,
    TaskRepository,
    UserConfRepository,
    UserRepository,
    WorkflowRepository,
)


def test_schema_signup_workspace_and_crud(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "test.db")
    db.initialize_schema()
    db.seed_defaults(cfg)  # create_demo_user false → no demo user

    users = UserRepository(db)
    assert users.authenticate("demo", "demo123") is None

    uid = users.create("muneeb", "muneeb@example.com", "secret123")
    db.seed_user_workspace(uid, cfg)
    user = users.authenticate("muneeb", "secret123")
    assert user is not None
    assert users.authenticate("muneeb", "wrong-password") is None
    stored = user["password"]
    assert stored != "secret123"
    assert stored.startswith("bcrypt$") or stored.startswith("sha256$") or len(stored) == 64
    assert "email" in user

    conf = UserConfRepository(db).get_map(user["user_id"])
    assert conf.get("dry_run") in ("0", "1")

    wfs = WorkflowRepository(db).list_for_user(user["user_id"])
    assert any(w["name"] == "Open Notepad Demo" for w in wfs)
    tasks = TaskRepository(db).list_for_workflow(wfs[0]["workflow_id"])
    assert len(tasks) >= 1

    cmd_id = NLPCommandRepository(db).create(
        "open chrome",
        "open_app",
        {"app": "chrome"},
        0.9,
        user_id=user["user_id"],
    )
    log_id = ExecutionLogRepository(db).create(
        "Success", 12, details={"ok": True}, user_id=user["user_id"], command_id=cmd_id
    )
    ScreenCaptureRepository(db).create(
        "/tmp/fake.png", log_id=log_id, width=100, height=50, element_found="Login"
    )
    assert ExecutionLogRepository(db).recent(user_id=user["user_id"], limit=5)
    stats = ExecutionLogRepository(db).stats(user["user_id"])
    assert stats["total"] >= 1
    assert "daily" in stats
    assert "failed" in stats

    try:
        users.create("muneeb", "other@example.com", "secret123")
        raised = False
    except Exception:
        raised = True
    assert raised

    db.close()
    reset_database_singleton()


def test_inactive_user_cannot_login(tmp_path: Path):
    reset_database_singleton()
    db = Database(tmp_path / "inactive.db")
    db.initialize_schema()
    users = UserRepository(db)
    uid = users.create("ghost", "ghost@example.com", "secret123")
    db.execute("UPDATE User SET is_active = 0 WHERE user_id = ?", (uid,))
    assert users.authenticate("ghost", "secret123") is None
    db.close()
    reset_database_singleton()
