"""Load YAML configuration and resolve project paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "default.yaml"


def load_config(path: Path | None = None) -> Dict[str, Any]:
    cfg_path = path or DEFAULT_CONFIG_PATH
    with cfg_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def resolve_path(relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def ensure_runtime_dirs(config: Dict[str, Any]) -> None:
    paths = config.get("paths", {})
    for key in ("data_dir", "captures_dir", "templates_dir", "logs_dir", "models_dir"):
        rel = paths.get(key)
        if rel:
            resolve_path(rel).mkdir(parents=True, exist_ok=True)
    db_file = paths.get("db_file")
    if db_file:
        resolve_path(db_file).parent.mkdir(parents=True, exist_ok=True)
