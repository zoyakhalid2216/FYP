from pathlib import Path

from src.config import load_config
from src.db.database import Database, reset_database_singleton
from src.db.repositories import UserRepository
from src.workflows.service import WorkflowService


def test_workflow_create_edit_delete_and_ownership(tmp_path: Path):
    reset_database_singleton()
    cfg = load_config()
    db = Database(tmp_path / "wf.db")
    db.initialize_schema()
    users = UserRepository(db)
    a = users.create("alice", "a@example.com", "secret123")
    b = users.create("bob", "b@example.com", "secret123")
    svc = WorkflowService(db)
    wid = svc.create_workflow(
        a,
        "Research Setup",
        tasks=[
            {"intent": "open_app", "target_app": "chrome", "params": {}},
            {"intent": "wait", "input_value": "1", "params": {"seconds": 1}},
        ],
    )
    wf = svc.get_workflow(wid)
    assert wf["name"] == "Research Setup"
    assert len(wf["tasks"]) == 2
    svc.rename_workflow(wid, "Daily Research")
    svc.save_tasks(
        wid,
        [
            {"intent": "open_app", "target_app": "chrome", "params": {}},
            {"intent": "search_web", "input_value": "AI", "params": {"query": "AI"}},
            {"intent": "wait", "input_value": "1", "params": {"seconds": 1}},
        ],
    )
    wf = svc.get_workflow(wid)
    assert wf["name"] == "Daily Research"
    assert len(wf["tasks"]) == 3
    assert svc.find_by_name(a, "Daily Research")
    assert svc.find_by_name(b, "Daily Research") is None
    listed = svc.list_workflows(a)
    assert any(w["workflow_id"] == wid for w in listed)
    assert not any(w["workflow_id"] == wid for w in svc.list_workflows(b))
    svc.delete_workflow(wid)
    assert all(w["workflow_id"] != wid for w in svc.list_workflows(a))
    db.close()
    reset_database_singleton()


def test_tasks_from_history():
    history = [
        {"action": "open_app", "app": "notepad"},
        {"action": "type_text", "text": "hello"},
    ]
    tasks = WorkflowService.tasks_from_action_history(None, history)  # type: ignore[arg-type]
    assert len(tasks) == 2
    assert tasks[0]["intent"] == "open_app"


def test_task_to_step_roundtrip():
    step = WorkflowService.task_to_step(
        {
            "intent": "click_text",
            "target_element": "Login",
            "params": {},
        }
    )
    assert step["intent"] == "click_text"
    assert step["entities"]["element"] == "Login"


def test_history_click_saves_label():
    tasks = WorkflowService.tasks_from_action_history(
        None,  # type: ignore[arg-type]
        [
            {"action": "click", "x": 10, "y": 20, "label": "Login With Odoo"},
        ],
    )
    assert tasks[0]["target_element"] == "Login With Odoo"
    assert tasks[0]["params"]["label"] == "Login With Odoo"


def test_empty_click_after_search_becomes_first_result():
    tasks = WorkflowService.fill_empty_clicks_after_search(
        [
            {"intent": "open_app", "target_app": "chrome", "params": {}},
            {
                "intent": "search_web",
                "input_value": "ucp student portal",
                "params": {"query": "ucp student portal"},
            },
            {"intent": "click_text", "target_element": "", "params": {"x": None, "y": None}},
            {"intent": "click_text", "target_element": "", "params": {"x": None, "y": None}},
        ]
    )
    clicks = [t for t in tasks if t.get("intent") == "click_text"]
    assert len(clicks) == 1
    assert clicks[0]["target_element"] == "__first_result__"
    step = WorkflowService.task_to_step(clicks[0])
    assert step["entities"].get("first_result") is True
    assert step["entities"].get("result_index") == 1


def test_empty_click_after_search_from_params_json():
    tasks = WorkflowService.fill_empty_clicks_after_search(
        [
            {
                "intent": "search_web",
                "input_value": "ucp",
                "params_json": '{"query": "ucp"}',
            },
            {
                "intent": "click_text",
                "target_element": "",
                "params_json": '{"x": null, "y": null}',
            },
        ]
    )
    clicks = [t for t in tasks if t.get("intent") == "click_text"]
    assert len(clicks) == 1
    step = WorkflowService.task_to_step(clicks[0])
    assert step["entities"]["element"] == "__first_result__"
    assert step["entities"].get("first_result") is True


def test_history_search_then_empty_click():
    tasks = WorkflowService.tasks_from_action_history(
        None,  # type: ignore[arg-type]
        [
            {"action": "open_app", "app": "chrome"},
            {"action": "search_google", "query": "ucp student portal"},
            {"action": "click", "x": None, "y": None},
        ],
    )
    clicks = [t for t in tasks if t.get("intent") == "click_text"]
    assert clicks
    assert clicks[0]["target_element"] == "__first_result__"
