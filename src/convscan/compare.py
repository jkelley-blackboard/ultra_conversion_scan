"""Post-scan compare: the baseline run (Originals) against the post run (copies), and the ID map."""
from __future__ import annotations

import re

SAME, DIFFERENT, EXPECTED, ACTION, NOT_CHECKED = "same", "different", "expected", "action", "not checked"

# Per-learner fields compared in S7. Scores compare within a small tolerance.
S7_FIELDS = ("attempts", "submitted", "open", "needs_grading", "highest_attempt_score", "manual_score", "exempt_ind")


def _rows(data, label, cid):
    return [r for r in data.get(label, []) if r.get("course_id") == cid]


def _one(data, label, cid):
    rs = _rows(data, label, cid)
    return rs[0] if rs else {}


def _eq(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 0.001
    return a == b


def norm(title) -> str:
    """Conversion strips HTML from titles ('<u>Chapter 1</u>' -> 'Chapter 1'): compare without it."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(title or ""))).strip().lower()


# Ultra keeps one overall grade, so the Original's weighted total has no counterpart.
_WEIGHTED = re.compile(r"weighted ?total|OutcomeDefinition\.WeightedTotal", re.I)


def _ext(pk):
    return f"_{pk}_1" if pk not in (None, "") else ""


def column_map(post: dict, orig_id: str) -> dict:
    """orig col_pk -> M2 row, for one course."""
    return {r["orig_col_pk"]: r for r in post.get("M2", []) if r.get("orig_course_id") == orig_id}


def compare_course(o: str, n: str, base: dict, post: dict, ran_base: set, ran_post: set):
    """Return (checks, learner_diffs) for one Original/copy pair."""
    checks, diffs = [], []

    def add(area, check, ov, nv, status, note=""):
        checks.append({"area": area, "check": check, "original": ov, "ultra": nv, "status": status, "note": note})

    if not _one(post, "S1", n):
        add("Course", "Copy exists", o, "not found", ACTION, f"No course with the ID {n}.")
        return checks, diffs

    def both(label):
        return label in ran_base and label in ran_post

    # The copy and convert task itself
    if "S13" in ran_post:
        tasks = [t for t in _rows(post, "S13", n) if t.get("task_type") == "BulkCopyAndConvertOperation"]
        if not tasks:
            add("Course", "Copy and convert task", "", "not found", NOT_CHECKED,
                "No bulk copy and convert task names this course (copied another way?).")
        else:
            t = tasks[-1]
            msg = (t.get("results_text") or "").replace("copy|copy.msg.clone.operation.success", "succeeded")
            add("Course", "Copy and convert task", "", t.get("status_label"),
                SAME if t.get("status") == "C" else ACTION,
                f"{str(t.get('end_date') or '')[:16]}, {t.get('seconds')} s. {msg}".strip())
        failed = [t for t in _rows(post, "S13", n) if t.get("status") == "E"]
        if failed:
            add("Course", "Failed system tasks", "", len(failed), ACTION,
                "; ".join(f"{t.get('task_type')}: {(t.get('results_text') or '')[:120]}" for t in failed))

    # Members
    if both("S2"):
        a, b = _one(base, "S2", o), _one(post, "S2", n)
        for col, label in (("members", "Active members"), ("students", "Students"),
                           ("in_progress", "Students in progress"), ("completed", "Students completed"),
                           ("students_disabled", "Disabled students")):
            ov, nv = a.get(col) or 0, b.get(col) or 0
            add("Members", label, ov, nv, SAME if ov == nv else DIFFERENT)

    # Content
    if both("S3"):
        a, b = dict(_one(base, "S3", o)), dict(_one(post, "S3", n))
        for x in (a, b):  # conversion turns assignments into Ultra assessments: count them together
            x["tests_assignments"] = (x.get("tests") or 0) + (x.get("assignments") or 0)
        for col, label, exact in (("tests_assignments", "Tests and assignments", True),
                                  ("scorm", "SCORM items", True), ("forum_links", "Discussion links", True),
                                  ("lti_items", "LTI tool links", True), ("items", "All items", False)):
            ov, nv = a.get(col) or 0, b.get(col) or 0
            if ov == nv:
                add("Content", label, ov, nv, SAME)
            elif not exact and nv > ov:
                add("Content", label, ov, nv, EXPECTED, "Conversion adds folders.")
            else:
                add("Content", label, ov, nv, DIFFERENT)

    # Grade columns
    if both("S4"):
        ov, nv = len(_rows(base, "S4", o)), len(_rows(post, "S4", n))
        weighted = sum(1 for r in _rows(base, "S4", o) if _WEIGHTED.search(r.get("title") or ""))
        if ov == nv:
            add("Grades", "Grade columns", ov, nv, SAME)
        elif nv == ov - weighted:
            add("Grades", "Grade columns", ov, nv, EXPECTED, "Ultra drops the weighted total column.")
        elif nv > ov:
            add("Grades", "Grade columns", ov, nv, EXPECTED, "Extra columns in Ultra are listed in the ID map.")
        else:
            add("Grades", "Grade columns", ov, nv, DIFFERENT, "Missing columns are listed in the ID map as not found.")

    # Groups: only groups with members or a job to do need restoring
    if both("S8"):
        og, ng = _rows(base, "S8", o), _rows(post, "S8", n)
        used = [g for g in og if (g.get("members") or 0) > 0 or (g.get("criteria_using_group") or 0) > 0
                or (g.get("test_exceptions_using_group") or 0) > 0]
        have = {norm(g.get("group_name")) for g in ng}
        missing = [g["group_name"] for g in used if norm(g.get("group_name")) not in have]
        if missing:
            add("Groups", "Groups in use", len(used), len(used) - len(missing), ACTION,
                f"Not carried over: {'; '.join(missing[:8])}. Run the group repair, then re-scan.")
        elif len(og) == len(ng):
            add("Groups", "Groups", len(og), len(ng), SAME)
        else:
            add("Groups", "Groups", len(og), len(ng), EXPECTED,
                "Only empty, unused groups are missing (conversion drops groups).")

    # Release rules: is every gated item still gated?
    if both("S9"):
        orows, nrows = _rows(base, "S9", o), _rows(post, "S9", n)
        o_items = {norm(r.get("item_title")): r.get("item_title") for r in orows}
        n_items = {norm(r.get("item_title")) for r in nrows}
        lost = [title for key, title in o_items.items() if key not in n_items]
        if lost:
            add("Release rules", "Gated items still gated", len(o_items), len(o_items) - len(lost), DIFFERENT,
                f"No condition in Ultra on: {'; '.join(lost[:8])}{' ...' if len(lost) > 8 else ''}.")
        else:
            add("Release rules", "Gated items still gated", len(o_items), len(o_items), SAME,
                "" if len(orows) == len(nrows) else
                f"Conditions {len(orows)} in the Original, {len(nrows)} in Ultra: conversion repeats some on the "
                "folders it adds. Compare item by item before release.")

    # Partial credit
    if both("S5c"):
        ov = len({r["question_pk"] for r in _rows(base, "S5c", o) if r.get("real_partial") is True})
        nv = len({r["question_pk"] for r in _rows(post, "S5c", n) if r.get("real_partial") is True})
        if nv >= ov:
            add("Tests", "Questions with partial-credit answer values", ov, nv, SAME)
        else:
            add("Tests", "Questions with partial-credit answer values", ov, nv, ACTION,
                f"{ov - nv} question(s) lost their answer values: run the partial-credit repair, then re-scan.")

    # Test exceptions
    if both("S12b"):
        ov, nv = len(_rows(base, "S12b", o)), len(_rows(post, "S12b", n))
        add("Tests", "Test exceptions", ov, nv, SAME if ov == nv else DIFFERENT)

    # Per-learner grades and attempts, columns matched through M2
    cmap = column_map(post, o)
    if both("S7") and "M2" in ran_post:
        new_rows = {(r["users_pk1"], r["col_pk"]): r for r in _rows(post, "S7", n)}
        compared = differing = missing = unmapped = 0
        learners = set()
        for r in _rows(base, "S7", o):
            m = cmap.get(r["col_pk"])
            new_col = m.get("new_col_pk") if m else None
            compared += 1
            if new_col in (None, ""):  # the column itself isn't matched yet: an ID map problem, not lost data
                unmapped += 1
                continue
            other = new_rows.get((r["users_pk1"], new_col))
            if other is None:
                missing += 1
                learners.add(r["users_pk1"])
                diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": r["col_pk"],
                              "new_col_pk": new_col or "", "field": "record", "original": "present", "copy": "missing"})
                continue
            bad = [f for f in S7_FIELDS if not _eq(r.get(f), other.get(f))]
            if bad:
                differing += 1
                learners.add(r["users_pk1"])
                for f in bad:
                    diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": r["col_pk"],
                                  "new_col_pk": new_col, "field": f, "original": r.get(f), "copy": other.get(f)})
        status = SAME if not (differing or missing or unmapped) else DIFFERENT
        note = []
        if differing or missing:
            note.append(f"{differing} differ and {missing} missing, for {len(learners)} learner(s); "
                        "details in data/diff_learner_records.csv.")
        if unmapped:
            note.append(f"{unmapped} sit in grade columns the ID map couldn't match one to one: "
                        "resolve those columns, then re-run.")
        add("Learner records", "Grade and attempt records matching", compared,
            compared - differing - missing - unmapped, status, " ".join(note))
    else:
        add("Learner records", "Grade and attempt records", "", "", NOT_CHECKED, "Needs S7 on both runs and M2.")

    # SCORM runtime state
    if both("S10"):
        new_rows = {(r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"]): r for r in _rows(post, "S10", n)}
        compared = same = unsaved = 0
        for r in _rows(base, "S10", o):
            compared += 1
            other = new_rows.get((r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"]))
            if other is None:
                diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                              "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']}",
                              "original": "present", "copy": "missing"})
            elif not r.get("runtime_md5") or not other.get("runtime_md5"):
                unsaved += 1
            elif r["runtime_md5"] == other["runtime_md5"]:
                same += 1
            else:
                diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                              "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']}",
                              "original": r["runtime_md5"], "copy": other["runtime_md5"]})
        bad = compared - same - unsaved
        add("SCORM", "SCORM records with the same resume state", compared, same, SAME if bad == 0 else DIFFERENT,
            (f"{unsaved} not yet saved by the player (not a difference). " if unsaved else "")
            + (f"{bad} differ or are missing." if bad else ""))
    else:
        add("SCORM", "SCORM resume state", "", "", NOT_CHECKED, "Needs S10 on both runs.")

    # Hidden columns that became visible
    if both("S4") and "M2" in ran_post:
        new_vis = {r["col_pk"]: r.get("visible_ind") for r in _rows(post, "S4", n)}
        shown = [m["title"] for m in cmap.values()
                 if m.get("visible_ind") == "N" and new_vis.get(m.get("new_col_pk")) == "Y"]
        if shown:
            add("Grades", "Hidden columns now visible", len(shown), len(shown), ACTION,
                "Decide whether to hide, remove or keep: " + "; ".join(shown[:8]) + (" ..." if len(shown) > 8 else ""))

    return checks, diffs


def id_map(o: str, n: str, base: dict, post: dict) -> list[dict]:
    """Course row, every Original column with its match, and columns that exist only in Ultra."""
    o_pk, n_pk = _one(base, "S1", o).get("crs_pk"), _one(post, "S1", n).get("crs_pk")
    rows = [{"orig_course_id": o, "new_course_id": n, "orig_id": _ext(o_pk), "new_id": _ext(n_pk),
             "kind": "course", "title": _one(base, "S1", o).get("course_name", ""), "attached_item": "",
             "match_status": "matched" if n_pk else "not found"}]
    mapped = set()
    for m in sorted(column_map(post, o).values(), key=lambda r: r["orig_col_pk"]):
        mapped.add(m.get("new_col_pk"))
        status = m.get("match_status", "")
        if status == "not found" and _WEIGHTED.search(m.get("title") or ""):
            status = "removed in Ultra (weighted total)"
        rows.append({"orig_course_id": o, "new_course_id": n, "orig_id": _ext(m["orig_col_pk"]),
                     "new_id": _ext(m.get("new_col_pk")), "kind": "grade column", "title": m.get("title", ""),
                     "attached_item": m.get("content_title") or "", "match_status": status})
    for r in _rows(post, "S4", n):
        if r["col_pk"] not in mapped:
            rows.append({"orig_course_id": o, "new_course_id": n, "orig_id": "", "new_id": _ext(r["col_pk"]),
                         "kind": "grade column", "title": r.get("title", ""),
                         "attached_item": r.get("content_title") or "", "match_status": "new in Ultra"})
    return rows
