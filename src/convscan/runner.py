"""Running the kit and saving results.

A runner only has to answer query(sql) -> (columns, rows). DdaRunner talks to the reporting
database directly; another runner (for example the Reporting Framework over REST) can replace it.
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import pathlib
import time
from typing import Protocol, Sequence

from . import __version__


class Runner(Protocol):
    def query(self, sql: str) -> tuple[list[str], Sequence[Sequence]]: ...


class DdaRunner:
    """Direct Data Access (PostgreSQL), read-only session. Credentials from DDA_* variables."""

    def __init__(self, statement_timeout_s: int = 900):
        import psycopg2

        missing = [v for v in ("DDA_HOST", "DDA_DBNAME", "DDA_USER", "DDA_PASSWORD") if not os.environ.get(v)]
        if missing:
            raise SystemExit("Missing environment variables: " + ", ".join(missing))
        self.conn = psycopg2.connect(
            host=os.environ["DDA_HOST"], port=os.environ.get("DDA_PORT", "5432"),
            dbname=os.environ["DDA_DBNAME"], user=os.environ["DDA_USER"],
            password=os.environ["DDA_PASSWORD"], application_name=f"convscan/{__version__}")
        self.conn.set_session(readonly=True, autocommit=True)
        with self.conn.cursor() as cur:
            cur.execute(f"set statement_timeout = {int(statement_timeout_s) * 1000}")

    def query(self, sql: str):
        with self.conn.cursor() as cur:
            cur.execute(sql)  # no parameters, so % in the SQL is literal
            return [d.name for d in cur.description], cur.fetchall()

    def close(self):
        self.conn.close()


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dt.datetime, dt.date)):
        return v.isoformat()
    if isinstance(v, memoryview):
        return v.tobytes().hex()
    return str(v)


def run_kit(runner: Runner, stmts: list[tuple[str, str]], out: pathlib.Path, meta: dict) -> dict:
    """Run each statement, write data/<label>.csv, and write run.json. Errors are recorded, not fatal."""
    data = out / "data"
    data.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, sql in stmts:
        t0 = time.time()
        try:
            cols, rows = runner.query(sql)
        except Exception as e:  # keep going: one failed query shouldn't lose the rest of the run
            results[label] = {"error": str(e).strip().splitlines()[0], "seconds": round(time.time() - t0, 1)}
            print(f"  {label:<5} ERROR  {results[label]['error']}")
            continue
        if "runtime_data" in cols:   # SCORM blobs: keep a fingerprint, never the learner's raw state
            from .scorm import summarize
            i = cols.index("runtime_data")
            extra = ["blob_md5", "blob_scos", "blob_locations"]
            rows = [tuple(r[:i]) + tuple(r[i + 1:]) + tuple(summarize(r[i])[k] for k in extra) for r in rows]
            cols = cols[:i] + cols[i + 1:] + extra
        with open(data / f"{label}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows([_cell(v) for v in r] for r in rows)
        results[label] = {"rows": len(rows), "seconds": round(time.time() - t0, 1)}
        print(f"  {label:<5} {len(rows):>8} rows  {results[label]['seconds']:>6.1f}s")
    run = {**meta, "convscan": __version__, "finished": dt.datetime.now().isoformat(timespec="seconds"),
           "queries": results}
    (out / "run.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    return run


def _coerce(v: str):
    if v == "":
        return None
    if v in ("true", "True", "t"):
        return True
    if v in ("false", "False", "f"):
        return False
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        return v


# Text columns stay strings even when they look like numbers (course IDs like 0042, a title "2024").
_TEXT = ("course_id", "title", "name", "path", "md5", "weights", "text", "handle", "named", "drawn_from",
         "locations")


def load_run(path: pathlib.Path) -> tuple[dict, dict[str, list[dict]]]:
    """Return (run.json, {label: rows}) with values coerced to numbers and booleans."""
    path = pathlib.Path(path)
    run = json.loads((path / "run.json").read_text(encoding="utf-8"))
    data = {}
    for f in sorted((path / "data").glob("*.csv")):
        with open(f, encoding="utf-8") as fh:
            data[f.stem] = [{k: (v if k.endswith(_TEXT) else _coerce(v)) for k, v in r.items()}
                            for r in csv.DictReader(fh)]
    return run, data
