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


def connection_settings(db: dict | None = None, env=None) -> dict:
    """Host, port, database and user: a DDA_* environment variable wins over the config's db block.

    Never includes the password; see password()."""
    env = os.environ if env is None else env
    db = db or {}
    out = {k: env.get(f"DDA_{k.upper()}") or db.get(k) for k in ("host", "port", "dbname", "user")}
    out["port"] = str(out["port"] or 5432)
    missing = [k for k in ("host", "dbname", "user") if not out[k]]
    if missing:
        raise SystemExit(
            "No database " + ", ".join(missing) + " given. Put them under db: in your config file "
            "(see config.example.yaml) and pass it with --config, or set " +
            ", ".join(f"DDA_{k.upper()}" for k in missing) + ".")
    return out


def password(env=None, prompt=None) -> str:
    """DDA_PASSWORD if set; otherwise ask, without echoing. Never stored anywhere."""
    env = os.environ if env is None else env
    if env.get("DDA_PASSWORD"):
        return env["DDA_PASSWORD"]
    import sys
    if prompt is None:
        if not sys.stdin.isatty():
            raise SystemExit("No password: set DDA_PASSWORD, or run convscan in a terminal so it can ask.")
        import getpass
        prompt = getpass.getpass
    return prompt("DDA password: ")


class DdaRunner:
    """Direct Data Access (PostgreSQL), read-only session.

    Connection details come from the config's db block or the DDA_* variables; the password from
    DDA_PASSWORD or a prompt."""

    def __init__(self, statement_timeout_s: int = 900, db: dict | None = None):
        import psycopg2

        conn = connection_settings(db)
        try:
            self.conn = psycopg2.connect(**conn, password=password(), connect_timeout=30,
                                         application_name=f"convscan/{__version__}")
        except psycopg2.OperationalError as e:
            detail = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
            raise SystemExit(f"Couldn't connect to {conn['dbname']} on {conn['host']}:{conn['port']} as "
                             f"{conn['user']}: {detail}")
        self.conn.set_session(readonly=True, autocommit=True)
        with self.conn.cursor() as cur:
            cur.execute(f"set statement_timeout = {int(statement_timeout_s) * 1000}")

    def query(self, sql: str):
        with self.conn.cursor() as cur:
            cur.execute(sql)  # no parameters, so % in the SQL is literal
            return [d.name for d in cur.description], cur.fetchall()

    def close(self):
        self.conn.close()


LAG_SQL = """select pg_is_in_recovery() as replica,
       pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() as caught_up,
       extract(epoch from now() - pg_last_xact_replay_timestamp())::float as since_last_replay_s"""


def replica_lag(runner: Runner) -> dict:
    """How far the reporting database (a PostgreSQL read replica) trails production.

    Returns {"lag_s": seconds or None, "note": text}. When the replica has applied everything it has
    received, the lag is 0: the time since the last replayed change only measures lag while changes
    are still waiting (on a quiet site it just grows). It can't see changes production hasn't sent
    yet. lag_s is None when the database won't say (for example, the DDA user may not be allowed to
    call these functions).
    """
    try:
        cols, rows = runner.query(LAG_SQL)
    except Exception as e:   # permission denied, or not PostgreSQL
        msg = str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__
        return {"lag_s": None, "note": f"could not read the replica lag ({msg})"}
    r = dict(zip(cols, rows[0]))
    if not r["replica"]:
        return {"lag_s": 0.0, "note": "not a replica (reads production directly)"}
    if r["caught_up"]:
        return {"lag_s": 0.0, "note": "caught up"}
    if r["since_last_replay_s"] is None:
        return {"lag_s": None, "note": "replica has not replayed any changes yet"}
    lag = round(max(r["since_last_replay_s"], 0.0), 1)
    return {"lag_s": lag, "note": f"{lag:,.0f} s behind, still applying changes"}


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
