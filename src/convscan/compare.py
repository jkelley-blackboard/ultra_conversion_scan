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


_TYPO = str.maketrans({"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"'})


def norm(title) -> str:
    """Conversion strips HTML from titles ('<u>Chapter 1</u>' -> 'Chapter 1') and plain-texts dashes
    and curly quotes: compare without either. Matches the normalization in the M2 SQL."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(title or "")).translate(_TYPO)).strip().lower()


# Ultra keeps one overall grade, so the Original's weighted total has no counterpart.
_WEIGHTED = re.compile(r"weighted ?total|OutcomeDefinition\.WeightedTotal", re.I)


# Content types that conversion renames: compare them under one name.
_HANDLER = {"resource/x-bb-assignment": "resource/x-bb-asmt-test-link", "resource/x-bb-lesson": "resource/x-bb-folder",
            "resource/x-bb-blankpage": "resource/x-bb-document"}   # a blank page becomes a folder plus a document

# Discussion links are renamed to the forum's own name in Ultra, so they can't be matched by title.
# Their number is compared in "Discussion links" and their conditions in the release-rule checks.
_RENAMED_BY_CONVERSION = {"resource/x-bb-forumlink"}


def _handler(h):
    return _HANDLER.get(h, h or "")


def _list(items, limit=8):
    items = [str(i) for i in items]
    return "; ".join(items[:limit]) + (f" (and {len(items) - limit} more)" if len(items) > limit else "")


def _crit_sig(r) -> tuple:
    """One release condition, normalized for comparing across a conversion. Index 9 is the groups."""
    def num(v):
        return "" if v in (None, "") else f"{float(v):g}"
    return (norm(r.get("item_title")), r.get("crit_type") or "", r.get("negate_ind") or "",
            num(r.get("min_score")), num(r.get("max_score")),
            str(r.get("start_date") or "")[:16], str(r.get("end_date") or "")[:16],
            norm(r.get("gate_column_title")), norm(r.get("reviewed_item_title")),
            norm(r.get("groups_named")), str(r.get("users_named") or ""))


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

    # Members (a copy value matching the Original now, after later enrollments, is fine)
    if both("S2"):
        a, b = _one(base, "S2", o), _one(post, "S2", n)
        now = _one(post, "S2_now", o) if "S2_now" in ran_post else None
        for col, label in (("members", "Active members"), ("students", "Students"),
                           ("in_progress", "Students in progress"), ("completed", "Students completed"),
                           ("students_disabled", "Disabled students")):
            ov, nv = a.get(col) or 0, b.get(col) or 0
            if ov == nv:
                add("Members", label, ov, nv, SAME)
            elif now is not None and (now.get(col) or 0) == nv:
                add("Members", label, ov, nv, EXPECTED, f"Matches the Original now ({nv}): changed after the pre-scan.")
            else:
                add("Members", label, ov, nv, DIFFERENT,
                    f"The Original now has {now.get(col) or 0}." if now is not None else "")

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

    # Content types: every type in the Original should still be there in at least the same number
    if both("S3c"):
        def inventory(rows):
            inv = {}
            for r in rows:
                h = _handler(r.get("cnthndlr_handle"))
                inv[h] = inv.get(h, 0) + (r.get("items") or 0)
            return inv
        oi, ni = inventory(_rows(base, "S3c", o)), inventory(_rows(post, "S3c", n))
        short = [f"{h.rsplit('/', 1)[-1]} {c} to {ni.get(h, 0)}" for h, c in sorted(oi.items()) if ni.get(h, 0) < c]
        added = [f"{h.rsplit('/', 1)[-1]} +{c - oi.get(h, 0)}" for h, c in sorted(ni.items()) if c > oi.get(h, 0)]
        add("Content", "Content types carried over", len(oi), len(oi) - len(short), DIFFERENT if short else SAME,
            ("Fewer in Ultra: " + "; ".join(short) + ". " if short else "")
            + ("Added by conversion: " + "; ".join(added) + "." if added else ""))

    # Item availability: anything hidden in the Original must stay hidden
    if both("S3b"):
        def avail(rows):
            out = {}
            for r in rows:
                if r.get("cnthndlr_handle") in _RENAMED_BY_CONVERSION:
                    continue
                key = (norm(r.get("title")), _handler(r.get("cnthndlr_handle")))
                y, n_ = out.get(key, (0, 0))
                out[key] = (y + (r.get("available_ind") != "N"), n_ + (r.get("available_ind") == "N"))
            return out
        oa, na = avail(_rows(base, "S3b", o)), avail(_rows(post, "S3b", n))
        titles = {(norm(r.get("title")), _handler(r.get("cnthndlr_handle"))): re.sub(r"<[^>]*>", "", r.get("title") or "")
                  for r in _rows(base, "S3b", o)}
        shown, hidden, missing = [], [], []
        for key, (oy, on) in oa.items():
            if key not in na:
                missing.append(titles[key])
                continue
            ny, nn = na[key]
            if on and nn < on:
                shown.append(titles[key])
            elif nn > on and ny < oy:
                hidden.append(titles[key])
        if shown:
            add("Content", "Hidden items now visible to learners", sum(v[1] for v in oa.values()), "", ACTION,
                "Visible in Ultra but hidden in the Original: " + _list(shown) + ". Hide them before release.")
        else:
            add("Content", "Hidden items still hidden", sum(v[1] for v in oa.values()),
                sum(v[1] for v in oa.values()), SAME)
        if hidden:
            add("Content", "Visible items now hidden", "", len(hidden), DIFFERENT,
                "Hidden in Ultra but visible in the Original: " + _list(hidden) + ".")
        if missing:
            add("Content", "Items not found by title in Ultra", len(oa), len(oa) - len(missing), DIFFERENT,
                _list(missing) + ". Conversion may have renamed or merged these: check them.")

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
                "folders it adds.")
        # Condition by condition: the same item, type, score range, dates, gate column, groups and users
        o_sigs = {_crit_sig(r): r for r in orows}
        n_sigs = {_crit_sig(r) for r in nrows}
        n_no_groups = {s[:9] + ("",) + s[10:] for s in n_sigs}
        lost = [r for s, r in o_sigs.items() if s not in n_sigs]
        group_only = [r for r in lost if r.get("groups_named") and
                      _crit_sig(r)[:9] + ("",) + _crit_sig(r)[10:] in n_no_groups]
        other = [r for r in lost if r not in group_only]
        if not lost:
            add("Release rules", "Conditions carried over exactly", len(o_sigs), len(o_sigs), SAME,
                "Same item, type, score range, dates, gate column, groups and named learners.")
        else:
            note = []
            if other:
                note.append(f"{len(other)} changed or missing, on: "
                            + _list(sorted({r.get('item_title') for r in other})) + ".")
            if group_only:
                note.append(f"{len(group_only)} lost only their group(s), on: "
                            + _list(sorted({r.get('item_title') for r in group_only}))
                            + ". The group repair should restore these.")
            add("Release rules", "Conditions carried over exactly", len(o_sigs), len(o_sigs) - len(lost),
                DIFFERENT if other else ACTION, " ".join(note))

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

    # Work in progress: open attempts and submissions waiting for grading, by type
    if both("S7"):
        kinds = (("resource/x-bb-assessment", "tests"), ("resource/x-bb-assignment", "assignments"),
                 ("resource/x-plugin-scormengine", "SCORM"))

        def wip(rows, field):
            total = sum(r.get(field) or 0 for r in rows)
            parts = []
            for handle, label in kinds:
                k = sum(r.get(field) or 0 for r in rows if r.get("score_provider_handle") == handle)
                if k:
                    parts.append(f"{k} {label}")
            return total, ", ".join(parts)

        for field, label in (("open", "Attempts in progress"), ("needs_grading", "Submissions waiting for grading")):
            ov, od = wip(_rows(base, "S7", o), field)
            nv, nd = wip(_rows(post, "S7", n), field)
            note = f"Original: {od}. Ultra: {nd}." if (ov or nv) else ""
            if ov == nv and od != nd:
                note += " (Assignments convert to Ultra assessments, so the split by type changes.)"
            add("Learner records", label, ov, nv, SAME if ov == nv else DIFFERENT, note.strip())

    # Per-learner grades and attempts, columns matched through M2
    cmap = column_map(post, o)
    if both("S7") and "M2" in ran_post:
        new_rows = {(r["users_pk1"], r["col_pk"]): r for r in _rows(post, "S7", n)}
        now_rows = {(r["users_pk1"], r["col_pk"]): r for r in _rows(post, "S7_now", o)}
        compared = differing = missing = unmapped = since = 0
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
            now = now_rows.get((r["users_pk1"], r["col_pk"]))
            if bad and now is not None and all(_eq(now.get(f), other.get(f)) for f in S7_FIELDS):
                since += 1   # the learner worked after the pre-scan, and the copy has that work
                continue
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
        if since:
            note.append(f"{since} changed after the pre-scan (learner activity) and match the Original now.")
        add("Learner records", "Grade and attempt records matching", compared,
            compared - differing - missing - unmapped, status, " ".join(note))
    else:
        add("Learner records", "Grade and attempt records", "", "", NOT_CHECKED, "Needs S7 on both runs and M2.")

    # SCORM runtime state
    if both("S10"):
        new_rows = {(r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"]): r for r in _rows(post, "S10", n)}
        def state(r):
            """The resume-state fingerprint: from the engine's tables if written out, else from its blob."""
            if r is None:
                return None
            return ("rt", r["runtime_md5"]) if r.get("runtime_md5") else \
                   (("blob", r["blob_md5"]) if r.get("blob_md5") else None)

        now_state = {(r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"]): state(r)
                     for r in _rows(post, "S10_now", o)}
        compared = same = unsaved = from_blob = 0
        for r in _rows(base, "S10", o):
            compared += 1
            key = (r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"])
            other = new_rows.get(key)
            if other is None:
                diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                              "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']}",
                              "original": "present", "copy": "missing"})
                continue
            a, b = state(r), state(other)
            if a is None or b is None or a[0] != b[0]:
                unsaved += 1
            elif a == b or now_state.get(key) == b:
                same += 1   # same as at the pre-scan, or same as the Original now (learner kept working)
                from_blob += a[0] == "blob"
            else:
                diffs.append({"course_id": o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                              "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']} resume state",
                              "original": r.get("blob_locations") or a[1], "copy": other.get("blob_locations") or b[1]})
        bad = compared - same - unsaved
        if bad:
            status = DIFFERENT
        elif compared and same == 0:   # nothing could be compared: don't call that "same"
            status = NOT_CHECKED
        else:
            status = SAME
        add("SCORM", "SCORM records with the same resume state", compared, same, status,
            ("No SCORM records in this course." if not compared else "")
            + (f"Bookmark, suspend data, status and score compared ({from_blob} from the engine's runtime "
               "record). " if same else "")
            + (f"{unsaved} could not be compared (no readable resume state on one side): check those in the "
               "learner view. " if unsaved else "")
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
