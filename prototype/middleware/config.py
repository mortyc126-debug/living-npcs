"""Загрузка YAML-конфига персоны."""

from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)
