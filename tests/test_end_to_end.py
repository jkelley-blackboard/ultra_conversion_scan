"""Offline end to end: render pre and post reports from invented runs (tests/sample_data.py).

Guards the rules, the compare and the templates together. If one of these fails after a change, the
sample's known losses are no longer being reported the way they should be.
"""
import csv

from convscan import config, report
from convscan.runner import load_run

import sample_data


def _render(tmp_path):
    pre_dir, post_dir = sample_data.write_runs(tmp_path)
    cfg = config.load(None)
    cfg["prepared_for"] = "Sample University"
    pre_run, pre = load_run(pre_dir)
    report.render_pre(pre_dir, pre_run, pre, cfg)
    post_run, post = load_run(post_dir)
    report.render_post(post_dir, post_run, post, pre_run, pre, cfg)
    return pre_dir / "reports", post_dir / "reports"


def test_preflight_flags_the_known_risks(tmp_path):
    pre, _ = _render(tmp_path)
    text = (pre / "DEMO101_preflight.md").read_text(encoding="utf-8")
    for expected in ("Release conditions that depend on groups", "Partial credit in tests that open the next step",
                     "Test attempts open now", "Grade columns hidden from learners", "Site conversion settings",
                     "Folders nested deeper than Ultra allows", "limit of 3 levels",
                     "Tests that draw questions from an undeployed test", "by: Module 1 Quiz"):
        assert expected in text, expected
    clean = (pre / "DEMO102_preflight.md").read_text(encoding="utf-8")
    assert "No blocking items found" in clean
    assert "Work waiting to be graded" in clean   # one submission waiting


def test_handoff_reports_losses_and_matches(tmp_path):
    _, post = _render(tmp_path)
    text = (post / "DEMO101_handoff.md").read_text(encoding="utf-8")
    assert "Not carried over: Advanced Stream" in text                       # group dropped
    assert "lost only their group(s)" in text                                # condition kept, group gone
    assert "1 question(s) lost their answer values" in text                  # partial credit reset
    assert "Hidden columns now visible" in text and "Placement Test" in text
    assert "| SCORM | SCORM records with the same resume state | 3 | 3 | Same |" in text   # HTML title normalized
    assert "| Learner records | Grade and attempt records matching | 9 | 9 | Same |" in text
    assert "Ultra drops the weighted total column." in text
    assert "Added by conversion: Document +2; Folder +2." in text            # plain names, not system values
    clean = (post / "DEMO102_handoff.md").read_text(encoding="utf-8")
    assert "Needs action" not in clean                                       # assignment -> assessment is fine
    assert "Ready to verify and release" in clean


def test_id_map(tmp_path):
    _, post = _render(tmp_path)
    with open(post / "idmap.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    status = {(r["orig_course_id"], r["title"]): r["match_status"] for r in rows}
    assert status[("DEMO101", "Weighted Total")] == "removed in Ultra (weighted total)"
    assert status[("DEMO102", "Case Study")] == "matched"
    assert [r for r in rows if r["kind"] == "course" and r["new_id"] == "_901_1"]


def test_handoff_warns_when_scanned_behind_the_replica(tmp_path):
    import json
    pre_dir, post_dir = sample_data.write_runs(tmp_path)
    run_json = post_dir / "run.json"
    run = json.loads(run_json.read_text(encoding="utf-8"))
    run["replica_lag"] = {"lag_s": 900.0, "note": "900 s behind, still applying changes"}
    run_json.write_text(json.dumps(run), encoding="utf-8")
    cfg = config.load(None)
    pre_run, pre = load_run(pre_dir)
    post_run, post = load_run(post_dir)
    report.render_post(post_dir, post_run, post, pre_run, pre, cfg)
    text = (post_dir / "reports" / "DEMO101_handoff.md").read_text(encoding="utf-8")
    assert "900 s behind" in text and "scan again before acting" in text


def test_no_em_dashes_in_reports(tmp_path):
    pre, post = _render(tmp_path)
    for f in list(pre.glob("*.md")) + list(post.glob("*.md")):
        assert "—" not in f.read_text(encoding="utf-8"), f.name
