"""Course facts and report rendering (Markdown through Jinja2 templates)."""
from __future__ import annotations

import csv
import json
import pathlib

import jinja2

from . import __version__, compare, rules


def _one(data, label, cid):
    return next((r for r in data.get(label, []) if r.get("course_id") == cid), {})


def _rows(data, label, cid):
    return [r for r in data.get(label, []) if r.get("course_id") == cid]


def course_facts(data: dict, cid: str) -> dict:
    """Plain counts for the 'The course' table. Missing queries give blanks, not zeros."""
    s1, s2, s3, s5b, s11 = (_one(data, q, cid) for q in ("S1", "S2", "S3", "S5b", "S11"))
    s9 = _rows(data, "S9", cid)
    return {
        "course_id": cid,
        "course_name": s1.get("course_name", ""),
        "available": {"Y": "Yes", "N": "No"}.get(s1.get("available_ind"), s1.get("available_ind", "")),
        "new_course_id": s1.get("expected_new_course_id", ""),
        "members": s2.get("members"), "staff": s2.get("staff"), "students": s2.get("students"),
        "in_progress": s2.get("in_progress"), "completed": s2.get("completed"),
        "students_disabled": s2.get("students_disabled"), "ip_lt30d": s2.get("ip_lt30d"),
        "ip_gt90d": s2.get("ip_gt90d"), "ip_never": s2.get("ip_never"),
        "item_count": s3.get("items"), "tests": s3.get("tests"), "assignments": s3.get("assignments"),
        "scorm": s3.get("scorm"), "forum_links": s3.get("forum_links"), "lti_items": s3.get("lti_items"),
        "gated_items": len({r["content_pk"] for r in s9}) if "S9" in data else None,
        "groups": len(_rows(data, "S8", cid)) if "S8" in data else None,
        "grade_columns": len(_rows(data, "S4", cid)) if "S4" in data else None,
        "partial_credit_questions": s5b.get("partial_credit_questions", 0) if "S5b" in data else None,
        "posts": s11.get("posts", 0) if "S11" in data else None,
    }


_SETTINGS = {
    "release_number": "Blackboard LMS version",
    "featureFlags:feature.course.release.condition.inheritance:Tenant":
        "Content takes the release conditions of its folder or learning module",
    "course.structure.max_level_of_nesting": "Levels of nested content (3 by default, 4 with the additional level)",
    "ultraui.converting.content.areas.to.learning.modules": "Content areas become learning modules",
    "ultraui.converting.folder.and.learning.module.descriptions.to.documents":
        "Folder and learning module descriptions become documents",
    "ultraui.converting.undeployed.tests.to.question.banks": "Undeployed tests become question banks",
}


def site_settings(data: dict) -> list[dict]:
    """S14 rows as labeled settings, for the reports. Empty if S14 wasn't run."""
    have = {r["registry_key"]: r.get("registry_value") for r in data.get("S14", [])}
    if not have:
        return []
    def show(v):
        if isinstance(v, str) and v.startswith("{"):   # a feature flag, stored as JSON
            try:
                v = json.loads(v).get("value", v)
            except ValueError:
                pass
        return {"true": "Yes", "false": "No", "none": "not set"}.get(str(v).lower(), v)
    return [{"label": label, "value": show(have.get(k))} for k, label in _SETTINGS.items()]


def _env(templates: pathlib.Path) -> jinja2.Environment:
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(str(templates)), trim_blocks=True,
                             lstrip_blocks=True, keep_trailing_newline=True, undefined=jinja2.StrictUndefined)
    env.filters["n"] = lambda v: "" if v is None else (f"{v:,}" if isinstance(v, int) else v)
    return env


def _course_ids(data: dict) -> list[str]:
    return sorted({r["course_id"] for r in data.get("S1", [])}, key=lambda c: (len(c), c))


def _ran(run: dict) -> set[str]:
    return {k for k, v in run.get("queries", {}).items() if "error" not in v}


def render_pre(run_dir: pathlib.Path, run: dict, data: dict, cfg: dict,
               reports_dir: pathlib.Path | None = None) -> list[pathlib.Path]:
    doc = rules.load_rules(cfg["rules"])
    env = _env(cfg["templates"])
    out = reports_dir or run_dir / "reports"
    out.mkdir(parents=True, exist_ok=True)
    ran = _ran(run)
    common = {"run": run, "cfg": cfg, "version": __version__,
              "not_checked_by_sql": doc.get("not_checked_by_sql", []), "severity": rules.SEVERITY,
              "settings": site_settings(data)}
    written, summary = [], []
    for cid in _course_ids(data):
        findings, not_checked = rules.evaluate(doc, data, cid, ran, cfg)
        facts = course_facts(data, cid)
        path = out / f"{_safe(cid)}_preflight.md"
        path.write_text(env.get_template("preflight.md.j2").render(
            c=facts, findings=findings, not_checked=not_checked, **common), encoding="utf-8")
        written.append(path)
        summary.append({"c": facts, "counts": {s: sum(1 for f in findings if f["severity"] == s) for s in rules.SEVERITY},
                        "decisions": sum(1 for f in findings if f["decision"]), "report": path.name})
    path = out / "batch_summary.md"
    path.write_text(env.get_template("batch_summary.md.j2").render(mode="pre", courses=summary, **common),
                    encoding="utf-8")
    return written + [path]


def render_post(run_dir: pathlib.Path, run: dict, data: dict, base_run: dict, base: dict,
                cfg: dict, reports_dir: pathlib.Path | None = None) -> list[pathlib.Path]:
    env = _env(cfg["templates"])
    labels = rules.load_rules(cfg["rules"]).get("labels") or {}   # plain names for content types
    out = reports_dir or run_dir / "reports"
    out.mkdir(parents=True, exist_ok=True)
    ran_base, ran_post = _ran(base_run), _ran(run)
    common = {"run": run, "base_run": base_run, "cfg": cfg, "version": __version__,
              "settings": site_settings(data)}
    written, summary, all_map, all_diffs = [], [], [], []
    for o, n in run["pairs"]:
        checks, diffs = compare.compare_course(o, n, base, data, ran_base, ran_post, labels=labels,
                                               students_copied=run.get("students_copied", True))
        idmap = compare.id_map(o, n, base, data)
        all_map += idmap
        all_diffs += diffs
        facts = course_facts(base, o)
        facts["new_course_id"] = n
        statuses = {s: sum(1 for c in checks if c["status"] == s) for s in
                    (compare.SAME, compare.EXPECTED, compare.DIFFERENT, compare.ACTION, compare.NOT_CHECKED)}
        map_counts = {}
        for r in idmap:
            if r["kind"] == "grade column":
                map_counts[r["match_status"]] = map_counts.get(r["match_status"], 0) + 1
        path = out / f"{_safe(o)}_handoff.md"
        path.write_text(env.get_template("handoff.md.j2").render(
            c=facts, checks=checks, statuses=statuses, idmap=idmap, map_counts=map_counts, **common),
            encoding="utf-8")
        written.append(path)
        summary.append({"c": facts, "statuses": statuses, "report": path.name})
    _write_csv(out / "idmap.csv", all_map,
               ["orig_course_id", "new_course_id", "kind", "orig_id", "new_id", "title", "attached_item", "match_status"])
    _write_csv(run_dir / "data" / "diff_learner_records.csv", all_diffs,
               ["course_id", "users_pk1", "orig_col_pk", "new_col_pk", "field", "original", "copy"])
    path = out / "batch_summary.md"
    path.write_text(env.get_template("batch_summary.md.j2").render(mode="post", courses=summary, **common),
                    encoding="utf-8")
    return written + [out / "idmap.csv", path]


def _write_csv(path: pathlib.Path, rows: list[dict], cols: list[str]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _safe(cid: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in cid)
