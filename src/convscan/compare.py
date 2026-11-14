"""Post-scan compare: the baseline run (Originals) against the post run (copies), and the ID map.

Each check_* function covers one area of the hand-off report. CHECKS sets their order, which is the
order of the report's checks table. To add a check, write a function that takes a Pair and calls
pair.add(), then list it in CHECKS.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SAME, DIFFERENT, EXPECTED, ACTION, NOT_CHECKED = "same", "different", "expected", "action", "not checked"

# Per-learner fields compared in S7. Scores compare within a small tolerance.
S7_FIELDS = ("attempts", "submitted", "open", "needs_grading", "highest_attempt_score", "manual_score", "exempt_ind")

_TYPO = str.maketrans({"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"'})

# Ultra keeps one overall grade, so the Original's weighted total has no counterpart.
_WEIGHTED = re.compile(r"weighted ?total|OutcomeDefinition\.WeightedTotal", re.I)

# Content types that conversion renames: compare them under one name.
_HANDLER = {"resource/x-bb-assignment": "resource/x-bb-asmt-test-link", "resource/x-bb-lesson": "resource/x-bb-folder",
            "resource/x-bb-blankpage": "resource/x-bb-document"}   # a blank page becomes a folder plus a document

# Discussion links take the forum's own name in Ultra, so they can't be matched by title. Their number
# is compared under "Discussion links", and their conditions in the release-condition checks.
_RENAMED_BY_CONVERSION = {"resource/x-bb-forumlink"}


# --- Helpers -------------------------------------------------------------------------------

def norm(title) -> str:
    """Conversion strips HTML from titles ('<u>Chapter 1</u>' -> 'Chapter 1') and plain-texts dashes
    and curly quotes: compare without either. Matches the normalization in the M2 SQL."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", "", str(title or "")).translate(_TYPO)).strip().lower()


def _rows(data, label, cid):
    return [r for r in data.get(label, []) if r.get("course_id") == cid]


def _one(data, label, cid):
    rs = _rows(data, label, cid)
    return rs[0] if rs else {}


def _eq(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return abs(a - b) < 0.001
    return a == b


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


def _without_groups(sig: tuple) -> tuple:
    return sig[:9] + ("",) + sig[10:]


def _ext(pk):
    return f"_{pk}_1" if pk not in (None, "") else ""


def column_map(post: dict, orig_id: str) -> dict:
    """Original column pk -> its M2 row, for one course."""
    return {r["orig_col_pk"]: r for r in post.get("M2", []) if r.get("orig_course_id") == orig_id}


# --- One Original and its copy -------------------------------------------------------------

@dataclass
class Pair:
    o: str                    # Original course_id
    n: str                    # copy course_id
    base: dict                # baseline run data {label: rows}
    post: dict                # post run data {label: rows}, including the *_now re-reads
    ran_base: set
    ran_post: set
    checks: list = field(default_factory=list)
    diffs: list = field(default_factory=list)   # per-learner differences, for data/diff_learner_records.csv

    def add(self, area, check, original, ultra, status, note=""):
        self.checks.append({"area": area, "check": check, "original": original, "ultra": ultra,
                            "status": status, "note": note})

    def both(self, label) -> bool:
        return label in self.ran_base and label in self.ran_post

    def orig(self, label):
        return _rows(self.base, label, self.o)

    def copy(self, label):
        return _rows(self.post, label, self.n)

    def now(self, label):
        """The Original re-read during the post-scan (label_now)."""
        return _rows(self.post, f"{label}_now", self.o)


# --- Checks, in report order ---------------------------------------------------------------

def check_copy_task(p: Pair):
    """The bulk copy and convert task, and any failed task on the copy (S13)."""
    if "S13" not in p.ran_post:
        return
    tasks = [t for t in p.copy("S13") if t.get("task_type") == "BulkCopyAndConvertOperation"]
    if not tasks:
        p.add("Course", "Copy and convert task", "", "not found", NOT_CHECKED,
              "No bulk copy and convert task names this course (copied another way?).")
    else:
        t = tasks[-1]
        msg = (t.get("results_text") or "").replace("copy|copy.msg.clone.operation.success", "succeeded")
        p.add("Course", "Copy and convert task", "", t.get("status_label"),
              SAME if t.get("status") == "C" else ACTION,
              f"{str(t.get('end_date') or '')[:16]}, {t.get('seconds')} s. {msg}".strip())
    failed = [t for t in p.copy("S13") if t.get("status") == "E"]
    if failed:
        p.add("Course", "Failed system tasks", "", len(failed), ACTION,
              "; ".join(f"{t.get('task_type')}: {(t.get('results_text') or '')[:120]}" for t in failed))


def check_members(p: Pair):
    """Member counts (S2). A copy value matching the Original now, after later enrollments, is fine."""
    if not p.both("S2"):
        return
    a, b = _one(p.base, "S2", p.o), _one(p.post, "S2", p.n)
    now = (p.now("S2") or [{}])[0] if "S2_now" in p.ran_post else None
    for col, label in (("members", "Active members"), ("students", "Students"),
                       ("in_progress", "Students in progress"), ("completed", "Students completed"),
                       ("students_disabled", "Disabled students")):
        ov, nv = a.get(col) or 0, b.get(col) or 0
        if ov == nv:
            p.add("Members", label, ov, nv, SAME)
        elif now is not None and (now.get(col) or 0) == nv:
            p.add("Members", label, ov, nv, EXPECTED, f"Matches the Original now ({nv}): changed after the pre-scan.")
        else:
            p.add("Members", label, ov, nv, DIFFERENT,
                  f"The Original now has {now.get(col) or 0}." if now is not None else "")


def check_content_counts(p: Pair):
    """Content counts (S3). Assignments become Ultra assessments, so they count with tests."""
    if not p.both("S3"):
        return
    a, b = dict(_one(p.base, "S3", p.o)), dict(_one(p.post, "S3", p.n))
    for x in (a, b):
        x["tests_assignments"] = (x.get("tests") or 0) + (x.get("assignments") or 0)
    for col, label, exact in (("tests_assignments", "Tests and assignments", True),
                              ("scorm", "SCORM items", True), ("forum_links", "Discussion links", True),
                              ("lti_items", "LTI tool links", True), ("items", "All items", False)):
        ov, nv = a.get(col) or 0, b.get(col) or 0
        if ov == nv:
            p.add("Content", label, ov, nv, SAME)
        elif not exact and nv > ov:
            p.add("Content", label, ov, nv, EXPECTED, "Conversion adds folders.")
        else:
            p.add("Content", label, ov, nv, DIFFERENT)


def check_content_types(p: Pair):
    """Every content type in the Original should still be there, at least as many times (S3c)."""
    if not p.both("S3c"):
        return

    def inventory(rows):
        inv = {}
        for r in rows:
            h = _handler(r.get("cnthndlr_handle"))
            inv[h] = inv.get(h, 0) + (r.get("items") or 0)
        return inv

    oi, ni = inventory(p.orig("S3c")), inventory(p.copy("S3c"))
    short = [f"{h.rsplit('/', 1)[-1]} {c} to {ni.get(h, 0)}" for h, c in sorted(oi.items()) if ni.get(h, 0) < c]
    added = [f"{h.rsplit('/', 1)[-1]} +{c - oi.get(h, 0)}" for h, c in sorted(ni.items()) if c > oi.get(h, 0)]
    p.add("Content", "Content types carried over", len(oi), len(oi) - len(short), DIFFERENT if short else SAME,
          ("Fewer in Ultra: " + "; ".join(short) + ". " if short else "")
          + ("Added by conversion: " + "; ".join(added) + "." if added else ""))


def check_availability(p: Pair):
    """Anything hidden in the Original must stay hidden (S3b), matched by normalized title and type."""
    if not p.both("S3b"):
        return

    def avail(rows):
        out = {}
        for r in rows:
            if r.get("cnthndlr_handle") in _RENAMED_BY_CONVERSION:
                continue
            key = (norm(r.get("title")), _handler(r.get("cnthndlr_handle")))
            y, n_ = out.get(key, (0, 0))
            out[key] = (y + (r.get("available_ind") != "N"), n_ + (r.get("available_ind") == "N"))
        return out

    oa, na = avail(p.orig("S3b")), avail(p.copy("S3b"))
    titles = {(norm(r.get("title")), _handler(r.get("cnthndlr_handle"))): re.sub(r"<[^>]*>", "", r.get("title") or "")
              for r in p.orig("S3b")}
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
    hidden_count = sum(v[1] for v in oa.values())
    if shown:
        p.add("Content", "Hidden items now visible to learners", hidden_count, "", ACTION,
              "Visible in Ultra but hidden in the Original: " + _list(shown) + ". Hide them before release.")
    else:
        p.add("Content", "Hidden items still hidden", hidden_count, hidden_count, SAME)
    if hidden:
        p.add("Content", "Visible items now hidden", "", len(hidden), DIFFERENT,
              "Hidden in Ultra but visible in the Original: " + _list(hidden) + ".")
    if missing:
        p.add("Content", "Items not found by title in Ultra", len(oa), len(oa) - len(missing), DIFFERENT,
              _list(missing) + ". Conversion may have renamed or merged these: check them.")


def check_grade_columns(p: Pair):
    """Grade column count (S4). Ultra drops the weighted total."""
    if not p.both("S4"):
        return
    ov, nv = len(p.orig("S4")), len(p.copy("S4"))
    weighted = sum(1 for r in p.orig("S4") if _WEIGHTED.search(r.get("title") or ""))
    if ov == nv:
        p.add("Grades", "Grade columns", ov, nv, SAME)
    elif nv == ov - weighted:
        p.add("Grades", "Grade columns", ov, nv, EXPECTED, "Ultra drops the weighted total column.")
    elif nv > ov:
        p.add("Grades", "Grade columns", ov, nv, EXPECTED, "Extra columns in Ultra are listed in the ID map.")
    else:
        p.add("Grades", "Grade columns", ov, nv, DIFFERENT, "Missing columns are listed in the ID map as not found.")


def check_groups(p: Pair):
    """Groups (S8). Only groups with members, conditions or test exceptions need restoring."""
    if not p.both("S8"):
        return
    og, ng = p.orig("S8"), p.copy("S8")
    used = [g for g in og if (g.get("members") or 0) > 0 or (g.get("criteria_using_group") or 0) > 0
            or (g.get("test_exceptions_using_group") or 0) > 0]
    have = {norm(g.get("group_name")) for g in ng}
    missing = [g["group_name"] for g in used if norm(g.get("group_name")) not in have]
    if missing:
        p.add("Groups", "Groups in use", len(used), len(used) - len(missing), ACTION,
              f"Not carried over: {'; '.join(missing[:8])}. Run the group repair, then re-scan.")
    elif len(og) == len(ng):
        p.add("Groups", "Groups", len(og), len(ng), SAME)
    else:
        p.add("Groups", "Groups", len(og), len(ng), EXPECTED,
              "Only empty, unused groups are missing (conversion drops groups).")


def check_release_conditions(p: Pair):
    """Release conditions (S9): every gated item still gated, then condition by condition."""
    if not p.both("S9"):
        return
    orows, nrows = p.orig("S9"), p.copy("S9")
    o_items = {norm(r.get("item_title")): r.get("item_title") for r in orows}
    n_items = {norm(r.get("item_title")) for r in nrows}
    lost_items = [title for key, title in o_items.items() if key not in n_items]
    if lost_items:
        p.add("Release conditions", "Gated items still gated", len(o_items), len(o_items) - len(lost_items),
              DIFFERENT, f"No condition in Ultra on: {_list(lost_items)}.")
    else:
        p.add("Release conditions", "Gated items still gated", len(o_items), len(o_items), SAME,
              "" if len(orows) == len(nrows) else
              f"Conditions {len(orows)} in the Original, {len(nrows)} in Ultra: conversion repeats some on the "
              "folders it adds.")

    o_sigs = {_crit_sig(r): r for r in orows}
    n_sigs = {_crit_sig(r) for r in nrows}
    n_no_groups = {_without_groups(s) for s in n_sigs}
    lost = [r for s, r in o_sigs.items() if s not in n_sigs]
    group_only = [r for r in lost if r.get("groups_named") and _without_groups(_crit_sig(r)) in n_no_groups]
    other = [r for r in lost if r not in group_only]
    if not lost:
        p.add("Release conditions", "Conditions carried over exactly", len(o_sigs), len(o_sigs), SAME,
              "Same item, type, score range, dates, gate column, groups and named learners.")
        return
    note = []
    if other:
        note.append(f"{len(other)} changed or missing, on: " + _list(sorted({r.get('item_title') for r in other})) + ".")
    if group_only:
        note.append(f"{len(group_only)} lost only their group(s), on: "
                    + _list(sorted({r.get('item_title') for r in group_only})) + ". The group repair should restore these.")
    p.add("Release conditions", "Conditions carried over exactly", len(o_sigs), len(o_sigs) - len(lost),
          DIFFERENT if other else ACTION, " ".join(note))


def check_partial_credit(p: Pair):
    """Questions whose answers carry partial-credit values (S5c). Conversion sets them to 0%."""
    if not p.both("S5c"):
        return
    ov = len({r["question_pk"] for r in p.orig("S5c") if r.get("real_partial") is True})
    nv = len({r["question_pk"] for r in p.copy("S5c") if r.get("real_partial") is True})
    if nv >= ov:
        p.add("Tests", "Questions with partial-credit answer values", ov, nv, SAME)
    else:
        p.add("Tests", "Questions with partial-credit answer values", ov, nv, ACTION,
              f"{ov - nv} question(s) lost their answer values: run the partial-credit repair, then re-scan.")


def check_question_sources(p: Pair):
    """Random-block and question-set draws must survive; new banks from undeployed tests are expected (S5e)."""
    if not p.both("S5e"):
        return
    a, b = _one(p.base, "S5e", p.o), _one(p.post, "S5e", p.n)
    ov, nv = a.get("block_draws") or 0, b.get("block_draws") or 0
    p.add("Tests", "Questions drawn through random blocks and question sets", ov, nv,
          SAME if ov == nv else DIFFERENT, "" if ov == nv else "Tests may now draw fewer questions: check them.")
    op, np_ = a.get("pools_and_banks") or 0, b.get("pools_and_banks") or 0
    if np_ != op:
        p.add("Tests", "Pools and question banks", op, np_, EXPECTED if np_ > op else DIFFERENT,
              "Undeployed tests became question banks (a site setting, listed below)." if np_ > op else "")


def check_question_types(p: Pair):
    """Real questions in tests (S5d). Presentation Only blocks and page breaks aren't questions."""
    if not p.both("S5d"):
        return
    orows = [r for r in p.orig("S5d") if r.get("question_type_code") not in (19, 20)]
    nrows = [r for r in p.copy("S5d") if r.get("question_type_code") not in (19, 20)]
    removed = sum(r.get("questions") or 0 for r in orows if r.get("removed_by_conversion") is True)
    ot = sum(r.get("questions") or 0 for r in orows)
    nt = sum(r.get("questions") or 0 for r in nrows)
    mc = sum(r.get("questions") or 0 for r in orows if r.get("question_type_code") == 1)
    if ot == nt:
        p.add("Tests", "Questions in tests", ot, nt, SAME,
              f"{mc} Multiple Choice question(s) are stored as Multiple Answer in Ultra (single answer)." if mc else "")
    elif removed and nt == ot - removed:
        p.add("Tests", "Questions in tests", ot, nt, ACTION,
              f"{removed} question(s) of types Ultra doesn't support were removed: replace them.")
    else:
        p.add("Tests", "Questions in tests", ot, nt, DIFFERENT,
              f"{removed} were of types Ultra removes." if removed else "")


def check_test_exceptions(p: Pair):
    """Test exceptions, per learner or group (S12b)."""
    if p.both("S12b"):
        ov, nv = len(p.orig("S12b")), len(p.copy("S12b"))
        p.add("Tests", "Test exceptions", ov, nv, SAME if ov == nv else DIFFERENT)


def check_work_in_progress(p: Pair):
    """Open attempts and submissions waiting for grading, by type (S7)."""
    if not p.both("S7"):
        return
    kinds = (("resource/x-bb-assessment", "tests"), ("resource/x-bb-assignment", "assignments"),
             ("resource/x-plugin-scormengine", "SCORM"))

    def wip(rows, fld):
        total = sum(r.get(fld) or 0 for r in rows)
        parts = [f"{k} {label}" for handle, label in kinds
                 if (k := sum(r.get(fld) or 0 for r in rows if r.get("score_provider_handle") == handle))]
        return total, ", ".join(parts)

    for fld, label in (("open", "Attempts in progress"), ("needs_grading", "Submissions waiting for grading")):
        ov, od = wip(p.orig("S7"), fld)
        nv, nd = wip(p.copy("S7"), fld)
        note = f"Original: {od}. Ultra: {nd}." if (ov or nv) else ""
        if ov == nv and od != nd:
            note += " (Assignments convert to Ultra assessments, so the split by type changes.)"
        p.add("Learner records", label, ov, nv, SAME if ov == nv else DIFFERENT, note.strip())


def check_learner_records(p: Pair):
    """Every learner's grades and attempts on every column (S7), columns matched through M2."""
    if not (p.both("S7") and "M2" in p.ran_post):
        p.add("Learner records", "Grade and attempt records", "", "", NOT_CHECKED,
              "The learner-level data or the column map is missing from one of the scans (run without --no-learner).")
        return
    cmap = column_map(p.post, p.o)
    new_rows = {(r["users_pk1"], r["col_pk"]): r for r in p.copy("S7")}
    now_rows = {(r["users_pk1"], r["col_pk"]): r for r in p.now("S7")}
    compared = differing = missing = unmapped = since = 0
    learners = set()
    for r in p.orig("S7"):
        compared += 1
        m = cmap.get(r["col_pk"])
        new_col = m.get("new_col_pk") if m else None
        if new_col in (None, ""):   # the column itself isn't matched yet: an ID map problem, not lost data
            unmapped += 1
            continue
        other = new_rows.get((r["users_pk1"], new_col))
        if other is None:
            missing += 1
            learners.add(r["users_pk1"])
            p.diffs.append({"course_id": p.o, "users_pk1": r["users_pk1"], "orig_col_pk": r["col_pk"],
                            "new_col_pk": new_col, "field": "record", "original": "present", "copy": "missing"})
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
                p.diffs.append({"course_id": p.o, "users_pk1": r["users_pk1"], "orig_col_pk": r["col_pk"],
                                "new_col_pk": new_col, "field": f, "original": r.get(f), "copy": other.get(f)})
    note = []
    if differing or missing:
        note.append(f"{differing} differ and {missing} missing, for {len(learners)} learner(s); "
                    "details in data/diff_learner_records.csv.")
    if unmapped:
        note.append(f"{unmapped} sit in grade columns the ID map couldn't match one to one: "
                    "resolve those columns, then re-run.")
    if since:
        note.append(f"{since} changed after the pre-scan (learner activity) and match the Original now.")
    p.add("Learner records", "Grade and attempt records matching", compared,
          compared - differing - missing - unmapped, SAME if not (differing or missing or unmapped) else DIFFERENT,
          " ".join(note))


def _scorm_state(r):
    """The resume-state fingerprint: from the engine's tables if written out, else from its runtime record."""
    if r is None:
        return None
    if r.get("runtime_md5"):
        return ("rt", r["runtime_md5"])
    return ("blob", r["blob_md5"]) if r.get("blob_md5") else None


def check_scorm(p: Pair):
    """SCORM resume state per learner, package and attempt (S10)."""
    if not p.both("S10"):
        p.add("SCORM", "SCORM resume state", "", "", NOT_CHECKED,
              "The learner-level SCORM data is missing from one of the scans (run without --no-learner).")
        return

    def key(r):
        return (r["users_pk1"], norm(r["scorm_title"]), r["attempt_no"])

    new_rows = {key(r): r for r in p.copy("S10")}
    now_state = {key(r): _scorm_state(r) for r in p.now("S10")}
    compared = same = unsaved = from_blob = 0
    for r in p.orig("S10"):
        compared += 1
        other = new_rows.get(key(r))
        if other is None:
            p.diffs.append({"course_id": p.o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                            "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']}",
                            "original": "present", "copy": "missing"})
            continue
        a, b = _scorm_state(r), _scorm_state(other)
        if a is None or b is None or a[0] != b[0]:
            unsaved += 1
        elif a == b or now_state.get(key(r)) == b:
            same += 1   # same as at the pre-scan, or same as the Original now (the learner kept working)
            from_blob += a[0] == "blob"
        else:
            p.diffs.append({"course_id": p.o, "users_pk1": r["users_pk1"], "orig_col_pk": "", "new_col_pk": "",
                            "field": f"SCORM {r['scorm_title']} attempt {r['attempt_no']} resume state",
                            "original": r.get("blob_locations") or a[1], "copy": other.get("blob_locations") or b[1]})
    bad = compared - same - unsaved
    status = DIFFERENT if bad else (NOT_CHECKED if compared and same == 0 else SAME)
    p.add("SCORM", "SCORM records with the same resume state", compared, same, status,
          ("No SCORM records in this course." if not compared else "")
          + (f"Bookmark, suspend data, status and score compared ({from_blob} from the engine's runtime "
             "record). " if same else "")
          + (f"{unsaved} could not be compared (no readable resume state on one side): check those in the "
             "learner view. " if unsaved else "")
          + (f"{bad} differ or are missing." if bad else ""))


def check_hidden_columns(p: Pair):
    """Grade columns hidden in the Original that are visible in Ultra (S4 through M2)."""
    if not (p.both("S4") and "M2" in p.ran_post):
        return
    new_vis = {r["col_pk"]: r.get("visible_ind") for r in p.copy("S4")}
    shown = [m["title"] for m in column_map(p.post, p.o).values()
             if m.get("visible_ind") == "N" and new_vis.get(m.get("new_col_pk")) == "Y"]
    if shown:
        p.add("Grades", "Hidden columns now visible", len(shown), len(shown), ACTION,
              "Decide whether to hide, remove or keep: " + _list(shown))


CHECKS = (check_copy_task, check_members, check_content_counts, check_content_types, check_availability,
          check_grade_columns, check_groups, check_release_conditions, check_partial_credit,
          check_question_sources, check_question_types, check_test_exceptions, check_work_in_progress,
          check_learner_records, check_scorm, check_hidden_columns)


def compare_course(o: str, n: str, base: dict, post: dict, ran_base: set, ran_post: set):
    """Return (checks, learner_diffs) for one Original and its copy."""
    p = Pair(o, n, base, post, ran_base, ran_post)
    if not _one(post, "S1", n):
        p.add("Course", "Copy exists", o, "not found", ACTION, f"No course with the ID {n}.")
        return p.checks, p.diffs
    for check in CHECKS:
        check(p)
    return p.checks, p.diffs


def id_map(o: str, n: str, base: dict, post: dict) -> list[dict]:
    """The course row, every Original column with its match, and columns that exist only in Ultra."""
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
