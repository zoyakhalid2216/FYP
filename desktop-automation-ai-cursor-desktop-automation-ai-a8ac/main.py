#!/usr/bin/env python3
"""Application entry point for Automate AI / AI Desktop Automation."""

from __future__ import annotations

import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication

from src.config import ensure_runtime_dirs, load_config, resolve_path
from src.db.database import get_database
from src.db.repositories import UserConfRepository, UserRepository
from src.gui.login_dialog import LoginDialog
from src.gui.main_window import MainWindow
from src.gui.styles import get_app_style
from src.pipeline import AutomationPipeline
from src.speech.recognizer import SpeechService
from src.vision.templates_seed import ensure_template_assets
from src.workflows.service import WorkflowService


def build_context(user: dict, *, config=None, db=None):
    config = config or load_config()
    ensure_runtime_dirs(config)
    ensure_template_assets(resolve_path(config.get("paths", {}).get("templates_dir", "assets/templates")))
    db = db or get_database(config)
    # Lazy NLP (no spaCy load until needed) keeps startup fast
    pipeline = AutomationPipeline(config, db)
    pipeline.apply_user_settings(user["user_id"])
    speech = SpeechService(config)
    return {
        "config": config,
        "db": db,
        "pipeline": pipeline,
        "speech": speech,
        "workflows": WorkflowService(db),
        "user": user,
    }


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    config = load_config()
    ensure_runtime_dirs(config)
    ensure_template_assets(resolve_path(config.get("paths", {}).get("templates_dir", "assets/templates")))
    db = get_database(config)

    app = QApplication(sys.argv)
    app_name = config.get("app", {}).get("name", "Automate AI")
    product = config.get("app", {}).get("product_name", "AI Desktop Automation")
    app.setApplicationName(app_name)
    app.setOrganizationName("S26CS089")
    app.setStyleSheet(get_app_style(config.get("ui", {}).get("theme", "light")))

    login = LoginDialog(
        UserRepository(db),
        conf_repo=UserConfRepository(db),
        app_name=app_name,
        product_name=product,
    )
    if login.exec_() != login.Accepted or not login.user:
        return 0

    # Apply user theme before main window paints
    conf = UserConfRepository(db).get_map(login.user["user_id"])
    theme = conf.get("theme") or config.get("ui", {}).get("theme", "light")
    app.setStyleSheet(get_app_style(theme))

    ctx = build_context(login.user, config=config, db=db)
    window = MainWindow(ctx)
    window.show()

    # Warm microphone in background after UI is up (faster first Mic click)
    QTimer.singleShot(300, lambda: ctx["speech"].warm_up())

    code = app.exec_()
    window.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
