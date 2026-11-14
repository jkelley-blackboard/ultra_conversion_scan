"""Defaults and optional YAML config."""
from __future__ import annotations

import pathlib

import yaml

PACKAGE = pathlib.Path(__file__).parent

DB_KEYS = ("host", "port", "dbname", "user")

DEFAULTS = {
    "db": {"host": None, "port": 5432, "dbname": None, "user": None},   # never the password
    "prepared_for": "TODO institution name",
    "new_id_suffix": "-7777",   # bulk copy and convert always puts a hyphen before the suffix
    "max_course_id_length": 15,
    "statement_timeout_s": 900,
    "learner_queries": True,
    "max_replica_lag_s": 300,   # post refuses to run while the reporting database trails by more
                                # than this (--ignore-lag overrides)
    "rules": None,
    "templates": None,
}


def load(path: str | None) -> dict:
    cfg = dict(DEFAULTS)
    cfg["db"] = dict(DEFAULTS["db"])
    if path:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        db = data.pop("db", None) or {}
        if "password" in db or "password" in data:
            raise SystemExit(f"{path}: don't put the database password in a config file. Leave it out and "
                             "convscan will ask for it, or set DDA_PASSWORD for this session.")
        unknown = set(db) - set(DB_KEYS)
        if unknown:
            raise SystemExit(f"{path}: unknown db setting(s): {', '.join(sorted(unknown))} "
                             f"(expected {', '.join(DB_KEYS)})")
        cfg["db"].update({k: v for k, v in db.items() if v is not None})
        cfg.update({k: v for k, v in data.items() if v is not None})
    cfg["rules"] = pathlib.Path(cfg["rules"]) if cfg["rules"] else PACKAGE / "rules" / "default.yaml"
    cfg["templates"] = pathlib.Path(cfg["templates"]) if cfg["templates"] else PACKAGE / "templates"
    return cfg
