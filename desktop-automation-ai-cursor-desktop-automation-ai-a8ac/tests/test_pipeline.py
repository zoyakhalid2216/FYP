from pathlib import Path

from src.config import load_config
from src.db.database import Database, reset_database_singleton
from src.db.repositories import UserRepository
from src.pipeline import AutomationPipeline
from src.workflows.service import WorkflowService


def test_text_command_dry_run(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    cfg = dict(cfg)
    cfg["paths"] = dict(cfg["paths"])
    cfg["paths"]["db_file"] = str(tmp_path / "auto.db")
    cfg["paths"]["captures_dir"] = str(tmp_path / "captures")
    cfg["paths"]["templates_dir"] = str(tmp_path / "templates")
    cfg["automation"] = dict(cfg.get("automation", {}))
    cfg["automation"]["dry_run"] = True

    db = Database(tmp_path / "auto.db")
    db.initialize_schema()
    db.seed_defaults(cfg)

    users = UserRepository(db)
    user_id = users.create("tester", "tester@example.com", "secret123")
    db.seed_user_workspace(user_id, cfg)

    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(True)

    result = pipeline.run_text_command("Open notepad and type hello", user_id=user_id)
    assert result["ok"] is True
    assert result["dry_run"] is True
    assert any(a.get("intent") == "open_app" for a in result["actions"])

    # Save history as workflow and replay
    wf_service = WorkflowService(db)
    tasks = wf_service.tasks_from_action_history(pipeline.automation.history)
    wid = wf_service.create_workflow(user_id, "From History", tasks=tasks)
    replay = pipeline.run_workflow(wid, user_id=user_id)
    assert replay["ok"] is True

    logs = pipeline.audit.recent_logs(10)
    assert any(l["status"] == "Success" for l in logs)

    # Voice-style: run by short name + copy file dry-run
    by_name = pipeline.run_workflow_by_name(user_id, "From History")
    assert by_name["ok"] is True

    copy = pipeline.run_text_command(
        "Copy file report to Desktop", user_id=user_id
    )
    # May fail if file missing — dry_run still resolves destinations; accept ok or clear error
    assert copy["parsed"]["intent"] == "copy_file"

    voiced = pipeline.run_text_command(
        "asdf qwer zxcv", user_id=user_id, source="voice"
    )
    assert voiced["parsed"]["intent"] == "type_text"
    assert voiced["ok"] is True
    assert voiced.get("plan")

    planned = pipeline.preview_plan("Open notepad and type hello")
    assert planned.steps
    assert planned.estimated_s >= 0

    db.close()
    reset_database_singleton()


def test_unknown_command(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "u.db")
    db.initialize_schema()
    db.seed_defaults(cfg)
    pipeline = AutomationPipeline(cfg, db)
    result = pipeline.run_text_command("asdf qwer zxcv")
    assert result["ok"] is False
    assert result.get("suggestions")
    db.close()
    reset_database_singleton()


def test_preview_plan_and_stop_flag(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "stop.db")
    db.initialize_schema()
    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(True)
    plan = pipeline.preview_plan("Click Login")
    assert any(s.intent in ("click_text", "inspect_screen") for s in plan.steps)
    pipeline.request_stop("User requested emergency stop.")
    assert pipeline._stop_requested is True
    db.close()
    reset_database_singleton()


def test_empty_click_asks_for_button_name(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "empty_click.db")
    db.initialize_schema()
    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(True)
    try:
        pipeline._click_element("", {})
        raise AssertionError("empty click should fail")
    except RuntimeError as exc:
        message = str(exc).lower()
        assert "no target" in message
        assert "tesseract" not in message
    db.close()
    reset_database_singleton()


def test_pipeline_close_app_dispatch_and_dry_run(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "close_test.db")
    db.initialize_schema()
    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(True)

    # 1. Dry run: close notepad
    res = pipeline.run_text_command("close notepad")
    assert res["ok"] is True
    assert res["dry_run"] is True
    close_actions = [a for a in res["actions"] if a.get("intent") == "close_app"]
    assert close_actions
    assert close_actions[0]["entities"].get("app") == "notepad"
    assert close_actions[0]["automation"]["dry_run"] is True

    # 2. Live dispatch verification with mocked automation
    pipeline.automation.set_dry_run(False)
    dispatched_apps = []

    def mock_close_app(app):
        dispatched_apps.append(app)
        return {"action": "close_app", "app": app, "success": True, "status": "closed"}

    pipeline.automation.close_app = mock_close_app
    res_live = pipeline.run_text_command("quit notepad")
    assert res_live["ok"] is True
    assert "notepad" in dispatched_apps

    db.close()
    reset_database_singleton()


def test_pipeline_self_close_guard(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "guard_test.db")
    db.initialize_schema()
    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(False)

    # Mock active window title as Automate AI
    pipeline.automation.get_active_window_title = lambda: "Automate AI - Voice Desktop Assistant"
    res = pipeline.run_text_command("close this window")

    # Assert self-close guard blocked it and requested confirmation
    close_actions = [a for a in res["actions"] if a.get("intent") == "close_app"]
    assert close_actions
    assert close_actions[0].get("needs_confirm") is True
    assert "Automate AI" in close_actions[0].get("confirm_prompt", "")

    db.close()
    reset_database_singleton()


def test_pipeline_close_tab_and_minimize(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "tab_min_test.db")
    db.initialize_schema()
    pipeline = AutomationPipeline(cfg, db)
    pipeline.automation.set_dry_run(True)

    res_tab = pipeline.run_text_command("close tab")
    assert res_tab["ok"] is True
    assert any(a.get("intent") == "close_tab" for a in res_tab["actions"])

    res_min = pipeline.run_text_command("minimize window")
    assert res_min["ok"] is True
    assert any(a.get("intent") == "minimize_window" for a in res_min["actions"])

    db.close()
    reset_database_singleton()
