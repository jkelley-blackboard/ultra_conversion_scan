"""convscan command line: check, pre, post, render, sql."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import config, kit, report
from .runner import DdaRunner, load_run, run_kit
from .scope import Scope


def _scope(a, cfg) -> Scope:
    suffix = cfg["new_id_suffix"] if a.suffix is None else a.suffix
    if a.manifest:
        return Scope.from_manifest(a.manifest, suffix)
    return Scope.from_node(a.node, suffix)


def _skip(a, cfg) -> set[str]:
    return kit.LEARNER if (a.no_learner or not cfg["learner_queries"]) else set()


def _new_out(path: str) -> pathlib.Path:
    out = pathlib.Path(path)
    if (out / "run.json").exists():
        raise SystemExit(f"{out} already holds a run; choose a new --out folder")
    out.mkdir(parents=True, exist_ok=True)
    return out


def cmd_check(a, cfg):
    stmts = kit.statements(kit.load_template(), "select 1", cfg["new_id_suffix"], only={"S0"})
    runner = DdaRunner(cfg["statement_timeout_s"])
    cols, rows = runner.query(stmts[0][1])
    if rows:
        print(f"{len(rows)} table/column(s) MISSING: the kit will not run as written")
        for r in rows:
            print("  ", r[0], r[1])
        sys.exit(1)
    print("S0: every table and column the kit uses is present")


def cmd_pre(a, cfg):
    scope = _scope(a, cfg)
    out = _new_out(a.out)
    stmts = kit.statements(kit.load_template(), scope.originals_sql(), scope.suffix, skip=_skip(a, cfg) | {"S0"})
    print(f"pre-scan, {scope.describe()}, {len(stmts)} queries -> {out}")
    runner = DdaRunner(cfg["statement_timeout_s"])
    run = run_kit(runner, stmts, out, {"mode": "pre", "name": out.name, "scope": scope.describe(),
                                       "suffix": scope.suffix, "pairs": scope.pairs})
    runner.close()
    _render(out, cfg)


def cmd_post(a, cfg):
    scope = _scope(a, cfg)
    base_dir = pathlib.Path(a.baseline)
    base_run, base = load_run(base_dir)
    if base_run.get("mode") != "pre":
        raise SystemExit(f"{base_dir} is not a pre-scan run")
    pairs = scope.pairs or [(c, c + scope.suffix) for c in sorted({r["course_id"] for r in base.get("S1", [])})]
    out = _new_out(a.out)
    stmts = kit.statements(kit.load_template(), scope.copies_sql(), scope.suffix, pairs_sql=scope.pairs_sql(),
                           skip=_skip(a, cfg) | {"S0"})
    print(f"post-scan, {scope.describe()}, {len(stmts)} queries -> {out}")
    runner = DdaRunner(cfg["statement_timeout_s"])
    run_kit(runner, stmts, out, {"mode": "post", "name": out.name, "scope": scope.describe(),
                                 "suffix": scope.suffix, "pairs": pairs, "baseline": str(base_dir.resolve())})
    runner.close()
    _render(out, cfg)


def _render(run_dir: pathlib.Path, cfg):
    run, data = load_run(run_dir)
    if run["mode"] == "pre":
        paths = report.render_pre(run_dir, run, data, cfg)
    else:
        base_run, base = load_run(pathlib.Path(run["baseline"]))
        paths = report.render_post(run_dir, run, data, base_run, base, cfg)
    print(f"wrote {len(paths)} file(s) in {run_dir / 'reports'}")


def cmd_render(a, cfg):
    _render(pathlib.Path(a.run), cfg)


def cmd_sql(a, cfg):
    scope = _scope(a, cfg)
    if a.scope == "original":
        stmts = kit.statements(kit.load_template(), scope.originals_sql(), scope.suffix, skip=_skip(a, cfg))
    else:
        stmts = kit.statements(kit.load_template(), scope.copies_sql(), scope.suffix,
                               pairs_sql=scope.pairs_sql(), skip=_skip(a, cfg))
    sys.stdout.write(kit.as_script(stmts))


def main(argv=None):
    p = argparse.ArgumentParser(prog="convscan", description=__doc__)
    p.add_argument("--config", help="YAML config (see config.example.yaml)")
    sub = p.add_subparsers(dest="cmd", required=True)

    def scoped(sp):
        g = sp.add_mutually_exclusive_group(required=True)
        g.add_argument("--manifest", help="CSV with orig_course_id,new_course_id")
        g.add_argument("--node", help="institutional hierarchy node batch_uid")
        sp.add_argument("--suffix", help="new course ID suffix (overrides config; '' compares a course with itself)")
        sp.add_argument("--no-learner", action="store_true", help="skip the per-learner queries")

    sub.add_parser("check", help="S0 schema check").set_defaults(fn=cmd_check)
    sp = sub.add_parser("pre", help="pre-scan the Originals and write pre-conversion reports")
    scoped(sp)
    sp.add_argument("--out", required=True, help="new run folder")
    sp.set_defaults(fn=cmd_pre)
    sp = sub.add_parser("post", help="post-scan the copies, compare with a baseline, write hand-off reports")
    scoped(sp)
    sp.add_argument("--baseline", required=True, help="the pre-scan run folder")
    sp.add_argument("--out", required=True, help="new run folder")
    sp.set_defaults(fn=cmd_post)
    sp = sub.add_parser("render", help="rebuild reports from a saved run (no database)")
    sp.add_argument("run")
    sp.set_defaults(fn=cmd_render)
    sp = sub.add_parser("sql", help="print the expanded SQL for one scope")
    scoped(sp)
    sp.add_argument("--scope", choices=["original", "copy"], default="original")
    sp.set_defaults(fn=cmd_sql)

    a = p.parse_args(argv)
    a.fn(a, config.load(a.config))


if __name__ == "__main__":
    main()
