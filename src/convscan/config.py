"""Defaults and optional YAML config."""
from __future__ import annotations

import pathlib

import yaml

PACKAGE = pathlib.Path(__file__).parent

DEFAULTS = {
    "prepared_for": "TODO institution name",
    "new_id_suffix": "-7777",   # bulk copy and convert always puts a hyphen before the suffix
    "max_course_id_length": 15,
    "statement_timeout_s": 900,
    "learner_queries": True,
    "rules": None,
    "templates": None,
}


def load(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    if path:
        with open(path, encoding="utf-8") as f:
            cfg.update({k: v for k, v in (yaml.safe_load(f) or {}).items() if v is not None})
    cfg["rules"] = pathlib.Path(cfg["rules"]) if cfg["rules"] else PACKAGE / "rules" / "default.yaml"
    cfg["templates"] = pathlib.Path(cfg["templates"]) if cfg["templates"] else PACKAGE / "templates"
    return cfg
