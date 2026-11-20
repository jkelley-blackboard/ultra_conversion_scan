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
                     "Test attempts open now", "Hidden grade columns that learners will see", "Site conversion settings",
                     "Folders nested deeper than Ultra allows", "3 levels of nested content",
                         "Further Reading (2 item(s))",
                     "Tests that draw questions from an undeployed test", "by: Module 1 Quiz"):
        assert expected in text, expected
    assert "| Blackboard LMS version | 4001.7.0-rel.4+a1cda0a |" in text
    assert "| Content takes the release conditions of its folder or learning module | Yes |" in text
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
    assert "| SCORM | SCORM records with the same resume state | 2 | 2 | Same |" in text   # HTML title normalized
    assert "| Learner records | Grade and attempt records matching | 6 | 6 | Same |" in text
    assert ("| Learner records | Unavailable students' records | 1 learner(s), 4 record(s) | "
            "1 learner(s), 4 record(s) | Same |") in text
    assert "compared as totals, not one by one" in text
    assert "Ultra drops the weighted total column." in text
    assert "Added by conversion: Document +2; Folder +2." in text            # plain names, not system values
    clean = (post / "DEMO102_handoff.md").read_text(encoding="utf-8")
    assert "Needs action" not in clean                                       # assignment -> assessment is fine
    assert "Ready to verify and release" in clean


def test_inactive_totals_that_differ_are_reported():
    from convscan import compare
    row = lambda c, grades, scorm: {"course_id": c, "state": "unavailable", "learners": 1, "grade_rows": grades,
                                    "attempts": grades, "open": 0, "needs_grading": 0, "scorm_registrations": scorm}
    base = {"S1": [{"course_id": "A"}], "S2b": [row("A", 3, 1)]}
    post = {"S1": [{"course_id": "A-7777"}], "S2b": [row("A-7777", 3, 0)], "S2b_now": [row("A", 3, 1)]}
    checks, _ = compare.compare_course("A", "A-7777", base, post, {"S2b"}, {"S2b", "S2b_now"})
    c = next(k for k in checks if k["check"] == "Unavailable students' records")
    assert c["status"] == compare.DIFFERENT and "SCORM records 1 to 0" in c["note"]
    # Access that changed after the pre-scan: the copy matches the Original now.
    post["S2b_now"] = [row("A", 3, 0)]
    checks, _ = compare.compare_course("A", "A-7777", base, post, {"S2b"}, {"S2b", "S2b_now"})
    assert next(k for k in checks if k["check"] == "Unavailable students' records")["status"] == compare.EXPECTED


def test_id_map(tmp_path):
    _, post = _render(tmp_path)
    with open(post / "idmap.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    status = {(r["orig_course_id"], r["title"]): r["match_status"] for r in rows}
    assert status[("DEMO101", "Weighted Total")] == "removed in Ultra (weighted total)"
    from convscan import compare
    assert compare._WEIGHTED.search("Total pondéré")   # the French name of the same column
    assert status[("DEMO102", "Case Study")] == "matched"
    course = next(r for r in rows if r["kind"] == "course" and r["orig_course_id"] == "DEMO101")
    assert list(rows[0]) == list(compare.ID_MAP_COLUMNS)
    assert (course["orig_pk1"], course["new_pk1"], course["table"]) == ("101", "901", "course_main")
    assert (course["orig_batch_uid"], course["new_batch_uid"]) == ("DEMO101", "DEMO101-7777")
    col = next(r for r in rows if r["title"] == "Module 1 Quiz")
    assert (col["orig_pk1"], col["new_pk1"], col["table"]) == ("1002", "9002", "gradebook_main")
    # The grade column ID and its item's content ID are different keys, in their own columns.
    assert col["orig_course_contents_pk1"] and col["orig_course_contents_pk1"] != col["orig_pk1"]
    assert col["new_course_contents_pk1"] and col["orig_batch_uid"] == ""
    total = next(r for r in rows if r["title"] == "Total")
    assert total["orig_course_contents_pk1"] == "" and total["new_course_contents_pk1"] == ""
    assert not any("_1" in r["orig_pk1"] + r["new_pk1"] for r in rows if r["orig_pk1"] or r["new_pk1"])   # numeric only
    handoff = (post / "DEMO101_handoff.md").read_text(encoding="utf-8")
    assert "External ID (`course_main.batch_uid`) | DEMO101 → DEMO101-7777" in handoff


def test_batch_uid_stays_text_when_loaded(tmp_path):
    """An external ID that looks like a number keeps its leading zeros."""
    import json
    run_dir = tmp_path / "r"
    (run_dir / "data").mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({"name": "r", "queries": {}}), encoding="utf-8")
    (run_dir / "data" / "S1.csv").write_text("course_id,crs_pk,batch_uid\n0042,7,00123\n", encoding="utf-8")
    _, data = load_run(run_dir)
    assert data["S1"][0]["batch_uid"] == "00123" and data["S1"][0]["course_id"] == "0042"


def test_custom_templates_folder_falls_back_for_new_templates(tmp_path):
    """A templates folder copied from an earlier version has no report_key.md.j2: the packaged one is used."""
    import shutil
    from convscan.config import PACKAGE
    custom = tmp_path / "my_templates"
    custom.mkdir()
    for name in ("preflight.md.j2", "handoff.md.j2", "batch_summary.md.j2"):
        shutil.copy(PACKAGE / "templates" / name, custom / name)
    pre_dir, _ = sample_data.write_runs(tmp_path / "runs")
    cfg = config.load(None)
    cfg["templates"] = custom
    pre_run, pre = load_run(pre_dir)
    report.render_pre(pre_dir, pre_run, pre, cfg)
    assert (pre_dir / "reports" / "REPORT_KEY.md").exists()


def test_scan_times_show_hour_minute_and_offset(tmp_path):
    assert report.stamp("2026-11-19T10:35:16-05:00") == "2026-11-19 10:35 (UTC-05:00)"
    assert report.stamp("2026-11-19T15:35:16+00:00") == "2026-11-19 15:35 (UTC+00:00)"
    assert report.stamp("2026-11-19T10:35:16") == "2026-11-19 10:35"          # older runs: no offset
    _, post = _render(tmp_path)
    head = (post / "DEMO101_handoff.md").read_text(encoding="utf-8")
    assert "**Post-scan:** 2026-12-01 10:00 (UTC-05:00) | **Baseline:** 2026-11-30 08:00 (UTC-05:00)" in head


def test_each_batch_has_a_report_key_for_its_reports(tmp_path):
    pre, post = _render(tmp_path)
    pre_key = (pre / "REPORT_KEY.md").read_text(encoding="utf-8")
    post_key = (post / "REPORT_KEY.md").read_text(encoding="utf-8")
    for key in (pre_key, post_key):
        assert key.startswith("# Report Key:") and "course_main.batch_uid" in key and "—" not in key
    assert "## Findings" in pre_key and "## Hand-off checks" not in pre_key
    assert "## Hand-off checks" in post_key and "## ID map" in post_key and "## Findings" not in post_key
    assert "course_contents.pk1" in post_key and "orig_course_contents_pk1" in post_key
    for out, report in ((pre, "DEMO101_preflight.md"), (post, "DEMO101_handoff.md"), (post, "batch_summary.md")):
        assert "(REPORT_KEY.md)" in (out / report).read_text(encoding="utf-8")
    assert "## IDs" not in (post / "batch_summary.md").read_text(encoding="utf-8")   # not repeated in the summary


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
