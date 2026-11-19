"""Defaults and optional YAML config."""
from __future__ import annotations

import pathlib

import yaml

PACKAGE = pathlib.Path(__file__).parent

DB_KEYS = ("host", "port", "dbname", "user")

DEFAULTS = {
    "db": {"host": None, "port": 5432, "dbname": None, "user": None},   # never the password
    "data_dir": "~/convscan/data",         # learner-level CSVs and run.json: local, not synced
    "reports_dir": "~/convscan/reports",   # what gets shared
    "reports_by_date": False,   # reports go in reports_dir/YYYY-MM-DD/<name>: the date the name starts
                                # with, else today
    "prepared_for": "TODO institution name",
    "new_id_prefix": "",        # copy course_id = prefix + Original course_id + suffix; bulk copy
    "new_id_suffix": "-7777",   # and convert always puts a hyphen between the ID and either one
    "max_course_id_length": 15,
    "statement_timeout_s": 900,
    "learner_queries": True,
    "max_replica_lag_s": 300,   # post refuses to run while the reporting database trails by more
                                # than this (--ignore-lag overrides)
    "nesting_what_if": True,    # the preflight says what the additional nesting level would change
                                # (false once the site's setting has been decided)
    "rules": None,
    "templates": None,
}


USER_CONFIG = pathlib.Path("~/convscan/config.yaml").expanduser()


def find() -> str | None:
    """The config to use when --config isn't given: CONVSCAN_CONFIG, ./convscan.yaml, ~/convscan/config.yaml."""
    import os
    env = os.environ.get("CONVSCAN_CONFIG")
    if env:
        if not pathlib.Path(env).expanduser().exists():
            raise SystemExit(f"CONVSCAN_CONFIG points to {env}, which doesn't exist")
        return str(pathlib.Path(env).expanduser())
    for p in (pathlib.Path("convscan.yaml"), USER_CONFIG):
        if p.exists():
            return str(p)
    return None


def starter(values: dict) -> str:
    """A starter config for 'convscan init'. Blank values become TODO; never a password."""
    import json

    def q(key):
        return json.dumps(values.get(key) or "TODO")   # JSON strings are valid YAML

    port = str(values.get("port") or 5432)
    return f"""# convscan config, made by 'convscan init'. Full list of settings: config.example.yaml in the repo.
# The DDA password is never stored here: convscan asks for it, or reads DDA_PASSWORD if set.

db:
  host: {q("host")}
  port: {int(port) if port.isdigit() else 5432}
  dbname: {q("dbname")}
  user: {q("user")}

prepared_for: {q("prepared_for")}

# Where runs go. Learner-level data stays in data_dir: keep it local, not synced or shared.
# Reports go to reports_dir: point it at a shared folder or a reports repository if you like.
data_dir: ~/convscan/data
reports_dir: ~/convscan/reports
"""


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
    base = pathlib.Path(path).resolve().parent if path else pathlib.Path.cwd()
    for key in ("data_dir", "reports_dir"):   # relative paths are relative to the config file
        p = pathlib.Path(str(cfg[key])).expanduser()
        cfg[key] = p if p.is_absolute() else base / p
    cfg["rules"] = pathlib.Path(cfg["rules"]) if cfg["rules"] else PACKAGE / "rules" / "default.yaml"
    cfg["templates"] = pathlib.Path(cfg["templates"]) if cfg["templates"] else PACKAGE / "templates"
    return cfg
