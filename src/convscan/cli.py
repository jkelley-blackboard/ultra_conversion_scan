"""convscan: read-only scans and reports for Original-to-Ultra course conversion.

Commands: init, check, pre, post, tasks, render, sql. See USER_GUIDE.md."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import config, kit, paths, report
from .runner import DdaRunner, load_run, replica_lag, run_kit
from .scope import Scope


def _scope(a, cfg) -> Scope:
    suffix = cfg["new_id_suffix"] if a.suffix is None else a.suffix
    prefix = cfg.get("new_id_prefix", "") if a.prefix is None else a.prefix
    if a.manifest:
        return Scope.from_manifest(a.manifest, suffix, prefix)
    return Scope.from_node(a.node, suffix, prefix)


def _skip(a, cfg) -> set[str]:
    return kit.LEARNER if (a.no_learner or not cfg["learner_queries"]) else set()


def _learners(a) -> tuple[str, str]:
    """(SQL filter, name recorded in run.json) for a pre-scan or the sql command."""
    if getattr(a, "all_learners", False):
        return kit.ALL_LEARNERS, "all"
    return kit.ACTIVE_LEARNERS, "active"


def _new_out(name: str, cfg) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a run's data and reports folders. Never overwrites a run or shared reports."""
    run_dir, reports_dir = paths.resolve(name, cfg)
    if (run_dir / "run.json").exists():
        raise SystemExit(f"{run_dir} already holds a run; choose a new --out name")
    if reports_dir.exists() and any(reports_dir.iterdir()):
        raise SystemExit(f"{reports_dir} already holds reports; choose a new --out name")
    why = paths.shared_location(run_dir)
    if why:
        print(f"WARNING: learner-level data will be written to {run_dir}, but {why}. Set data_dir in "
              "your config to a local folder that isn't synced or shared.", file=sys.stderr)
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, reports_dir


def cmd_check(a, cfg):
    stmts = kit.statements(kit.load_template(), "select 1", cfg["new_id_suffix"], only={"S0"})
    runner = DdaRunner(cfg["statement_timeout_s"], cfg["db"])
    cols, rows = runner.query(stmts[0][1])
    if rows:
        print(f"{len(rows)} table/column(s) MISSING: the kit will not run as written")
        for r in rows:
            print("  ", r[0], r[1])
        sys.exit(1)
    print("S0: every table and column the kit uses is present")
    print(f"replica lag: {replica_lag(runner)['note']}")
    runner.close()


def cmd_pre(a, cfg):
    scope = _scope(a, cfg)
    filt, learners = _learners(a)
    stmts = kit.statements(kit.load_template(), scope.originals_sql(), scope.suffix, skip=_skip(a, cfg) | {"S0"},
                           learners=filt, prefix=scope.prefix)
    runner = DdaRunner(cfg["statement_timeout_s"], cfg["db"])
    out, reports_dir = _new_out(a.out, cfg)
    print(f"pre-scan, {scope.describe()}, {len(stmts)} queries, learners: {learners} -> {out}")
    run_kit(runner, stmts, out, {"mode": "pre", "name": out.name, "scope": scope.describe(),
                                 "prefix": scope.prefix, "suffix": scope.suffix, "pairs": scope.pairs,
                                 "learners": learners,
                                 "reports_dir": str(reports_dir)})
    runner.close()
    _render(out, cfg)


def cmd_post(a, cfg):
    scope = _scope(a, cfg)
    base_dir = paths.resolve(a.baseline, cfg)[0]
    if not (base_dir / "run.json").exists():
        raise SystemExit(f"no pre-scan run at {base_dir} (give the pre-scan's --out name, or its folder)")
    base_run, base = load_run(base_dir)
    if base_run.get("mode") != "pre":
        raise SystemExit(f"{base_dir} is not a pre-scan run")
    pairs = scope.pairs or [(c, scope.new_id(c)) for c in sorted({r["course_id"] for r in base.get("S1", [])})]
    runner = DdaRunner(cfg["statement_timeout_s"], cfg["db"])
    # The reporting database is a read replica. After a large batch of copies it can trail production,
    # and a scan of half-replicated copies reports losses that aren't real.
    lag = replica_lag(runner)
    print(f"replica lag: {lag['note']}")
    if lag["lag_s"] is not None and lag["lag_s"] > cfg["max_replica_lag_s"] and not a.ignore_lag:
        runner.close()
        raise SystemExit(f"the reporting database is more than {cfg['max_replica_lag_s']} s behind; "
                         "wait and try again (or pass --ignore-lag)")
    out, reports_dir = _new_out(a.out, cfg)
    # The same learners the baseline read, whatever their state now.
    filt, learners = kit.learner_filter(base_run, base, pairs), base_run.get("learners", "all")
    stmts = kit.statements(kit.load_template(), scope.copies_sql(), scope.suffix, pairs_sql=scope.pairs_sql(),
                           skip=_skip(a, cfg) | {"S0"}, learners=filt, prefix=scope.prefix)
    # The Originals as they are now: learners keep working after the pre-scan, so the compare
    # accepts a copy value that matches either the baseline or the Original now. --no-reread skips
    # this second read of the Originals; the compare then uses the baseline alone.
    if not a.no_reread:
        stmts += [(f"{label}_now", sql) for label, sql in
                  kit.statements(kit.load_template(), scope.originals_sql(), scope.suffix,
                                 only=kit.NOW, skip=_skip(a, cfg), learners=filt, prefix=scope.prefix)]
    print(f"post-scan, {scope.describe()}, {len(stmts)} queries, learners: as the baseline ({learners}) -> {out}")
    run_kit(runner, stmts, out, {"mode": "post", "name": out.name, "scope": scope.describe(),
                                 "prefix": scope.prefix, "suffix": scope.suffix, "pairs": pairs,
                                 "baseline": str(base_dir.resolve()),
                                 "learners": learners, "replica_lag": lag, "reports_dir": str(reports_dir)})
    runner.close()
    _render(out, cfg)


def _render(run_dir: pathlib.Path, cfg):
    """Write the reports to the folder run.json names, plus a copy of run.json (no learner data in it)."""
    run, data = load_run(run_dir)
    reports_dir = pathlib.Path(run.get("reports_dir") or run_dir / "reports")
    if run["mode"] == "pre":
        written = report.render_pre(run_dir, run, data, cfg, reports_dir)
    else:
        base_run, base = load_run(pathlib.Path(run["baseline"]))
        written = report.render_post(run_dir, run, data, base_run, base, cfg, reports_dir)
    (reports_dir / "run.json").write_text((run_dir / "run.json").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {len(written) + 1} file(s) in {reports_dir}")


def cmd_render(a, cfg):
    run_dir = paths.resolve(a.run, cfg)[0]
    if not (run_dir / "run.json").exists():
        raise SystemExit(f"no run at {run_dir}")
    _render(run_dir, cfg)


def cmd_tasks(a, cfg):
    """Show the copy and convert task for each pair (S13 on the copies); --wait polls until all finish."""
    import time

    scope = _scope(a, cfg)
    if not scope.pairs:
        raise SystemExit("tasks needs --manifest (a node scope has no copy list until the copies exist)")
    sql = dict(kit.statements(kit.load_template(), scope.copies_sql(), scope.suffix, only={"S13"},
                              prefix=scope.prefix))["S13"]
    runner = DdaRunner(cfg["statement_timeout_s"], cfg["db"])
    deadline = time.time() + a.timeout * 60
    while True:
        cols, rows = runner.query(sql)
        recs = [dict(zip(cols, r)) for r in rows]
        done = 0
        print(time.strftime("%H:%M:%S"))
        for orig, new in scope.pairs:
            t = [x for x in recs if x["course_id"] == new and x["task_type"] == "BulkCopyAndConvertOperation"]
            other = [x for x in recs if x["course_id"] == new and x["task_type"] != "BulkCopyAndConvertOperation"
                     and x["status"] not in ("C",)]
            if not t:
                print(f"  {orig:<20} -> {new:<20} no copy task yet")
                continue
            t = t[-1]
            done += t["status"] in ("C", "E") and not other
            pending = f", {len(other)} follow-on task(s) not complete" if other else ""
            print(f"  {orig:<20} -> {new:<20} {t['status_label']:<12} {t['end_date'] or ''} "
                  f"{(t['results_text'] or '')[:60]}{pending}")
        if not a.wait or done == len(scope.pairs):
            break
        if time.time() > deadline:
            raise SystemExit("timed out waiting for tasks")
        time.sleep(60)
    if a.wait:
        print("all copy and convert tasks finished; checking the reporting database has caught up")
        while True:
            lag = replica_lag(runner)
            print(f"  {time.strftime('%H:%M:%S')} replica lag: {lag['note']}")
            if lag["lag_s"] is None:
                print("  lag unknown: check that the copies look complete before running post")
                break
            if lag["lag_s"] <= cfg["max_replica_lag_s"]:
                print("  ready for post")
                break
            if time.time() > deadline:
                runner.close()
                raise SystemExit("timed out waiting for the reporting database to catch up")
            time.sleep(30)
    runner.close()


def cmd_sql(a, cfg):
    scope = _scope(a, cfg)
    filt = _learners(a)[0]
    if a.scope == "original":
        stmts = kit.statements(kit.load_template(), scope.originals_sql(), scope.suffix, skip=_skip(a, cfg),
                               learners=filt, prefix=scope.prefix)
    else:
        stmts = kit.statements(kit.load_template(), scope.copies_sql(), scope.suffix,
                               pairs_sql=scope.pairs_sql(), skip=_skip(a, cfg), learners=filt,
                               prefix=scope.prefix)
    sys.stdout.write(kit.as_script(stmts))


def cmd_init(a, cfg):
    """Ask for the connection details and write a starter config. Never overwrites."""
    target = pathlib.Path(a.path).expanduser() if a.path else config.USER_CONFIG
    if target.exists():
        raise SystemExit(f"{target} already exists; edit it, or give another path")
    print(f"Creating {target}. Press Enter to leave a value as TODO; you can edit the file later.\n"
          "The password is never saved: convscan asks for it each time.")
    def ask(question):
        try:
            return input(question).strip()
        except EOFError:          # no one to answer (piped or scripted): leave it as TODO
            print()
            return ""
    values = {"host": ask("DDA host: "), "port": ask("Port [5432]: ") or "5432",
              "dbname": ask("Database name: "), "user": ask("Read-only DDA user: "),
              "prepared_for": ask("Institution name, for the reports: ")}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(config.starter(values), encoding="utf-8")
    print(f"Wrote {target}.\nNext: convscan check")


def main(argv=None):
    from . import __version__

    p = argparse.ArgumentParser(prog="convscan", description=__doc__)
    p.add_argument("--version", action="version", version=f"convscan {__version__}")
    p.add_argument("--config", help="YAML config. If omitted: CONVSCAN_CONFIG, then ./convscan.yaml, "
                                    "then ~/convscan/config.yaml (made by 'convscan init')")
    sub = p.add_subparsers(dest="cmd", required=True)

    def scoped(sp):
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--manifest", help="CSV with orig_course_id,new_course_id")
        g.add_argument("--node", help="institutional hierarchy node batch_uid")
        sp.add_argument("--suffix", help="new course ID suffix (overrides config; '' compares a course with itself)")
        sp.add_argument("--prefix", help="new course ID prefix, for example ULTRA- (overrides config)")
        sp.add_argument("--no-learner", action="store_true", help="skip the per-learner queries")

    sp = sub.add_parser("init", help="create a starter config (asks for the connection details)")
    sp.add_argument("path", nargs="?", help="where to write it (default ~/convscan/config.yaml)")
    sp.set_defaults(fn=cmd_init)
    sub.add_parser("check", help="test the connection, the schema (S0) and the replica lag").set_defaults(fn=cmd_check)
    all_learners = ("read every enabled student's records one by one, not only students in progress "
                    "(unavailable and disabled students are otherwise only totalled)")
    sp = sub.add_parser("pre", help="pre-scan the Originals and write pre-conversion reports")
    scoped(sp)
    sp.add_argument("--all-learners", action="store_true", help=all_learners)
    sp.add_argument("--out", required=True,
                    help="run name (data under data_dir, reports under reports_dir), or a folder path")
    sp.set_defaults(fn=cmd_pre)
    sp = sub.add_parser("post", help="post-scan the copies, compare with a baseline, write hand-off reports")
    scoped(sp)
    sp.add_argument("--baseline", required=True, help="the pre-scan's run name, or its folder")
    sp.add_argument("--out", required=True,
                    help="run name (data under data_dir, reports under reports_dir), or a folder path")
    sp.add_argument("--ignore-lag", action="store_true",
                    help="run even if the reporting database trails production by more than max_replica_lag_s")
    sp.add_argument("--no-reread", action="store_true",
                    help="don't read the Originals again; compare with the baseline alone (quicker, but "
                         "changes to the Originals after the pre-scan show as Different, not Expected)")
    sp.set_defaults(fn=cmd_post)
    sp = sub.add_parser("tasks", help="show (or --wait for) the copy and convert task of each course")
    scoped(sp)
    sp.add_argument("--wait", action="store_true",
                    help="poll every minute until every task finishes, then until the reporting database catches up")
    sp.add_argument("--timeout", type=int, default=120, help="minutes to wait (default 120)")
    sp.set_defaults(fn=cmd_tasks)
    sp = sub.add_parser("render", help="rebuild reports from a saved run (no database)")
    sp.add_argument("run", help="the run's name, or its data folder")
    sp.set_defaults(fn=cmd_render)
    sp = sub.add_parser("sql", help="print the expanded SQL for one scope")
    scoped(sp)
    sp.add_argument("--scope", choices=["original", "copy"], default="original")
    sp.add_argument("--all-learners", action="store_true", help=all_learners)
    sp.set_defaults(fn=cmd_sql)

    a = p.parse_args(argv)
    if a.cmd == "init":
        a.fn(a, None)
        return
    path = a.config or config.find()
    if path and not a.config:
        print(f"using config {path}", file=sys.stderr)
    a.fn(a, config.load(path))


if __name__ == "__main__":
    main()
