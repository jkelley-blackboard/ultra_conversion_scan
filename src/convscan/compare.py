"""Post-scan compare: the baseline run (Originals) against the post run (copies), and the ID map.

Each check_* function covers one area of the hand-off report. CHECKS sets their order, which is the
order of the report's checks table. To add a check, write a function that takes a Pair and calls
pair.add(), then list it in CHECKS.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field

SAME, DIFFERENT, EXPECTED, ACTION, NOT_CHECKED = "same", "different", "expected", "action", "not checked"
# Expected, should fix: conversion always does this and learners lose nothing, so it doesn't block
# release, but it should be put right after the course opens (tier 2 in the pre-conversion report,
# or tier 3 for wrapped items).
EXPECTED_FIX = "expected fix"
STATUSES = (SAME, EXPECTED, EXPECTED_FIX, DIFFERENT, ACTION, NOT_CHECKED)
IMPROVEMENT = "Learners lose nothing, so this doesn't block release: fix it after the course opens."

# Per-learner fields compared in S7. Scores compare within a small tolerance.
S7_FIELDS = ("attempts", "submitted", "open", "needs_grading", "highest_attempt_score", "manual_score", "exempt_ind")

_TYPO = str.maketrans({"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "«": "<", "»": ">"})

# Ultra keeps one overall grade, so the Original's weighted total has no counterpart.
_WEIGHTED = re.compile(r"weighted ?total|total pond[ée]r[ée]|OutcomeDefinition\.WeightedTotal", re.I)
# The Original's default Total column. Conversion keeps it as a calculated "Total" when the course has
# graded items, and removes it when there is nothing to total.
_DEFAULT_TOTAL = re.compile(r"^(OutcomeDefinition\.Total\.title|total)$", re.I)

# Content types conversion drops (the pre-conversion rules course_links and tool_links).
_DROPPED_BY_CONVERSION = {"resource/x-bb-courselink", "resource/x-bb-toollink"}

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
    # Typography first: conversion turns « » into < >, which then reads as a tag, so both sides must
    # go through the same steps. Then tags, then entities (titles can hold &quot; and &amp;).
    text = html.unescape(re.sub(r"<[^>]*>", "", str(title or "").translate(_TYPO)))
    return re.sub(r"\s+", " ", text).strip().lower()


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


def _without_users(sig: tuple) -> tuple:
    """The condition without its named learners (index 10)."""
    return sig[:10] + ("",)


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
    labels: dict = field(default_factory=dict)  # plain names for system values (the rule file's labels)
    students_copied: bool = True                # False: copied without user activity (post --no-students)
    checks: list = field(default_factory=list)
    diffs: list = field(default_factory=list)   # per-learner differences, for data/diff_learner_records.csv

    def name(self, value) -> str:
        """A plain name for a system value, or its last part if there's no label."""
        return self.labels.get(value) or str(value).rsplit("/", 1)[-1]

    def add(self, area, check, original, ultra, status, note="", details=None):
        self.checks.append({"area": area, "check": check, "original": original, "ultra": ultra,
                            "status": status, "note": note, "details": details or []})

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
                       ("in_progress", "Students in progress"), ("completed", "Students completed or expired"),
                       ("students_disabled", "Disabled students")):
        ov, nv = a.get(col) or 0, b.get(col) or 0
        if not p.students_copied and ov != nv:
            # Copied without user activity: students stay behind, other members (instructors and
            # other course roles) are kept.
            if col == "members":
                staff = (a.get("members") or 0) - (a.get("students") or 0)
                if nv == staff:
                    p.add("Members", label, ov, nv, EXPECTED,
                          f"Copied without students: the {nv} non-student member(s) were kept.")
                    continue
            elif nv == 0:
                p.add("Members", label, ov, nv, EXPECTED, "Copied without students.")
                continue
            p.add("Members", label, ov, nv, DIFFERENT, "Copied without students, but this count doesn't fit that.")
            continue
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
    # The Original's undeployed tests have no content item, so S3 doesn't count them; conversion adds one
    # for each, in a hidden folder. Those extra tests are expected, not a difference.
    undeployed = len(undeployed_tests_folder(p)) if p.both("S3b") else 0
    for col, label, exact in (("tests_assignments", "Tests and assignments", True),
                              ("scorm", "SCORM items", True), ("forum_links", "Discussion links", True),
                              ("lti_items", "LTI tool links", True), ("items", "All items", False)):
        ov, nv = a.get(col) or 0, b.get(col) or 0
        if ov == nv:
            p.add("Content", label, ov, nv, SAME)
        elif not exact and nv > ov:
            p.add("Content", label, ov, nv, EXPECTED, "Conversion adds folders.")
        elif col == "tests_assignments" and undeployed and nv - ov == undeployed:
            p.add("Content", label, ov, nv, EXPECTED,
                  f"The {undeployed} extra test(s) are the Original's undeployed tests, which conversion puts in a "
                  "hidden folder (see \"Undeployed tests in a hidden folder\").")
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
    short = [f"{p.name(h)} {c} to {ni.get(h, 0)}" for h, c in sorted(oi.items()) if ni.get(h, 0) < c]
    added = [f"{p.name(h)} +{c - oi.get(h, 0)}" for h, c in sorted(ni.items()) if c > oi.get(h, 0)]
    dropped = sorted({p.name(h) for h, c in oi.items() if h in _DROPPED_BY_CONVERSION and ni.get(h, 0) < c})
    p.add("Content", "Content types carried over", len(oi), len(oi) - len(short), DIFFERENT if short else SAME,
          ("Fewer in Ultra: " + "; ".join(short) + ". " if short else "")
          + ("Known loss: conversion drops " + " and ".join(x.lower() + "s" for x in dropped)
             + "; recreate the ones learners need. " if dropped else "")
          + ("Added by conversion: " + "; ".join(added) + "." if added else ""))


_CONTAINERS = ("resource/x-bb-folder", "resource/x-bb-lesson")


def check_nesting(p: Pair):
    """Folders and learning modules nested too deep for the site (S3d), found again in the copy (S3b).
    Conversion moves each one up to sit directly in its learning module, with the items directly in
    it (a too-deep folder inside another comes out beside it), so each is compared on its direct items."""
    if not (p.both("S3d") and p.both("S3b")):
        return
    rows = p.orig("S3d")
    if not rows:
        return
    limit = int(rows[0].get("max_level") or 0)
    otree, ntree = p.orig("S3b"), p.copy("S3b")

    def children(tree):
        """content_pk -> direct children. By parent ID when the scan has it; else by path and depth
        (older runs), which can mix up two folders that share a path."""
        kids = {}
        if tree and "parent_pk" in tree[0]:
            for r in tree:
                kids.setdefault(r.get("parent_pk"), []).append(r)
            return lambda node: kids.get(node.get("content_pk"), [])
        return lambda node: [r for r in tree if str(r.get("path") or "").startswith(str(node.get("path")) + " / ")
                             and int(r.get("depth") or 0) == int(node.get("depth") or 0) + 1]

    o_kids, n_kids = children(otree), children(ntree)

    def items(kids):
        return sum(1 for r in kids if r.get("cnthndlr_handle") not in _CONTAINERS)

    def shown(path):
        path = str(path or "")
        return path[len("ROOT / "):] if path.startswith("ROOT / ") else path

    o_nodes = {r.get("content_pk"): r for r in otree}
    n_folders = [r for r in ntree if _handler(r.get("cnthndlr_handle")) == "resource/x-bb-folder"]
    details, ok = [], 0
    for f in rows:
        node = o_nodes.get(f.get("content_pk")) or {"content_pk": f.get("content_pk"), "path": f.get("path"),
                                                     "depth": int(f.get("ultra_level") or 1) - 1}
        okids = o_kids(node)
        o_titles, o_items = {norm(r.get("title")) for r in okids}, items(okids)
        cands = [r for r in n_folders if norm(r.get("title")) == norm(f.get("title"))]
        # Best: most of the same direct children; then one that fits the limit; then the shallowest.
        best = max(cands, key=lambda r: (len({norm(k.get("title")) for k in n_kids(r)} & o_titles),
                                         int(r.get("depth") or 0) < limit, -int(r.get("depth") or 0)),
                   default=None)
        row = {"original_path": f.get("path"), "original_level": f.get("ultra_level"), "items_original": o_items,
               "ultra_path": "", "ultra_level": "", "items_ultra": ""}
        if best is None:
            row["result"] = "Not found in the copy"
        else:
            # Every direct child counts on the copy side: too-deep folders come out beside it, so a
            # folder still inside it is a converted item (a blank page becomes a folder and a document).
            n_level, n_items = int(best.get("depth") or 0), len(n_kids(best))   # the copy's root is level 0
            row.update(ultra_path=shown(best.get("path")), ultra_level=n_level, items_ultra=n_items)
            if n_level >= limit:
                row["result"] = f"Still too deep for {limit} levels"
            elif n_items < o_items:
                row["result"] = f"Moved up, {o_items - n_items} item(s) fewer"
            else:
                row["result"] = "Moved up, items kept"
                ok += 1
        details.append(row)
    note = (f"This site allows {limit} levels of nested content. Conversion moves each folder nested too deep up to "
            "sit directly in its learning module, with the items directly in it: see \"Folders moved up by "
            "conversion\" below for where each one is now.")
    if ok == len(rows):
        note += " " + IMPROVEMENT
    p.add("Content", "Folders moved up by conversion", len(rows), ok,
          EXPECTED_FIX if ok == len(rows) else DIFFERENT, note, details=details)


_TEST_LINK = "resource/x-bb-asmt-test-link"


def undeployed_tests_folder(p: Pair) -> list[dict]:
    """Folders conversion adds at the top of the copy to hold the Original's undeployed tests: hidden,
    holding only tests, with no container of that title in the Original. Returns their direct items."""
    o_titles = {norm(r.get("title")) for r in p.orig("S3b") if r.get("cnthndlr_handle") in _CONTAINERS}
    tree = p.copy("S3b")
    items = []
    for f in tree:
        if (f.get("cnthndlr_handle") in _CONTAINERS and int(f.get("depth") or 0) == 1
                and f.get("available_ind") == "N" and norm(f.get("title")) not in o_titles):
            kids = [r for r in tree if r.get("parent_pk") == f.get("content_pk")]
            if kids and all(r.get("cnthndlr_handle") == _TEST_LINK for r in kids):
                items += [dict(r, folder_title=f.get("title")) for r in kids]
    return items


def _wrappers(tree) -> list[str]:
    """Folders holding exactly one item of the same title: what conversion makes of a blank page or a
    folder description ('Note' becomes folder 'Note' around document 'Note')."""
    out = []
    for f in tree:
        if f.get("cnthndlr_handle") not in _CONTAINERS:
            continue
        kids = [r for r in tree if r.get("parent_pk") == f.get("content_pk")]
        if (len(kids) == 1 and kids[0].get("cnthndlr_handle") not in _CONTAINERS
                and norm(kids[0].get("title")) == norm(f.get("title"))):
            out.append(re.sub(r"<[^>]*>", "", f.get("title") or ""))
    return out


def check_added_folders(p: Pair):
    """Folders conversion adds that a tidy course removes (S3b): the hidden folder of undeployed tests,
    and single-item folders wrapped around a document."""
    if not p.both("S3b"):
        return
    tests = undeployed_tests_folder(p)
    if tests:
        folders = sorted({t["folder_title"] for t in tests})
        p.add("Content", "Undeployed tests in a hidden folder", 0, len(tests), EXPECTED_FIX,
              f"Conversion put the Original's {len(tests)} undeployed test(s) in the hidden folder "
              f"{_list(folders)}; any grade columns they have come with them. Learners can't see the folder. "
              f"Keep it hidden or remove it. {IMPROVEMENT}")
    copy_tree = p.copy("S3b")
    if copy_tree and "parent_pk" in copy_tree[0]:
        o_wrapped = _wrappers(p.orig("S3b"))
        extra = list(_wrappers(copy_tree))
        for t in o_wrapped:        # the Original's own single-item folders aren't conversion's doing
            if t in extra:
                extra.remove(t)
        if extra:
            p.add("Content", "Items wrapped in a folder by conversion", 0, len(extra), EXPECTED_FIX,
                  f"Each sits in a folder of its own name, so learners open the folder, then the item: "
                  f"{_list(extra)}. {IMPROVEMENT}")


def check_availability(p: Pair):
    """Anything hidden in the Original must stay hidden (S3b), matched by normalized title and type.
    Folders and learning modules count as one type, because conversion turns content areas into
    learning modules. An empty folder or content area missing from the copy is expected: conversion
    doesn't carry empty containers over."""
    if not p.both("S3b"):
        return

    def kind(r):
        h = r.get("cnthndlr_handle")
        return "container" if h in _CONTAINERS else _handler(h)

    def avail(rows):
        out = {}
        for r in rows:
            # Renamed types compare elsewhere; dropped types (course and tool links) are reported as a
            # known loss by "Content types carried over", so they aren't "not found" here too.
            if r.get("cnthndlr_handle") in _RENAMED_BY_CONVERSION | _DROPPED_BY_CONVERSION:
                continue
            key = (norm(r.get("title")), kind(r))
            y, n_ = out.get(key, (0, 0))
            out[key] = (y + (r.get("available_ind") != "N"), n_ + (r.get("available_ind") == "N"))
        return out

    otree = p.orig("S3b")
    oa, na = avail(otree), avail(p.copy("S3b"))
    titles = {(norm(r.get("title")), kind(r)): html.unescape(re.sub(r"<[^>]*>", "", r.get("title") or ""))
              for r in otree}
    # Containers with nothing in them, by key (only when the scan has parent IDs).
    parents = {r.get("parent_pk") for r in otree} if otree and "parent_pk" in otree[0] else None
    empty = {(norm(r.get("title")), "container") for r in otree
             if parents is not None and kind(r) == "container" and r.get("content_pk") not in parents}
    shown, hidden, missing, empty_missing = [], [], [], []
    for key, (oy, on) in oa.items():
        if key not in na:
            (empty_missing if key in empty else missing).append(titles[key])
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
    if empty_missing:
        p.add("Content", "Empty folders not carried over", len(empty_missing), 0, EXPECTED,
              "Empty in the Original, so conversion didn't create them: " + _list(empty_missing) + ".")


def check_grade_columns(p: Pair):
    """Grade column count (S4). Ultra drops the weighted total, and the default total when the course
    has nothing to total."""
    if not p.both("S4"):
        return
    ov, nv = len(p.orig("S4")), len(p.copy("S4"))
    weighted = sum(1 for r in p.orig("S4") if _WEIGHTED.search(r.get("title") or ""))
    totals = sum(1 for r in p.orig("S4") if _DEFAULT_TOTAL.search(r.get("title") or ""))
    if ov == nv:
        p.add("Grades", "Grade columns", ov, nv, SAME)
    elif nv == ov - weighted:
        p.add("Grades", "Grade columns", ov, nv, EXPECTED, "Ultra drops the weighted total column.")
    elif nv == ov - weighted - totals:
        p.add("Grades", "Grade columns", ov, nv, EXPECTED,
              "Ultra drops the weighted total, and the default total column when nothing in the course is graded.")
    elif nv > ov:
        undeployed = {t.get("content_pk") for t in undeployed_tests_folder(p)} if p.both("S3b") else set()
        k = sum(1 for r in p.copy("S4") if r.get("content_pk") in undeployed and r.get("content_pk") is not None)
        if k:
            p.add("Grades", "Grade columns", ov, nv, EXPECTED_FIX,
                  f"{k} column(s) belong to the undeployed tests conversion put in a hidden folder (hidden from "
                  "learners); they go if that folder is removed. Extra columns are listed in the ID map.")
        else:
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
    # Copied without students: a condition naming learners comes over naming none of them, because
    # those learners aren't in the copy. Not a conversion loss; the copy with learners shows it.
    n_no_users = {_without_users(s) for s in n_sigs}
    users_only = [r for r in lost if r not in group_only and not p.students_copied and r.get("users_named")
                  and _without_users(_crit_sig(r)) in n_no_users]
    other = [r for r in lost if r not in group_only and r not in users_only]
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
    if users_only:
        note.append(f"{len(users_only)} lost only their named learners, on: "
                    + _list(sorted({r.get('item_title') for r in users_only}))
                    + ". Copied without students, so those learners aren't in the copy: check these again on "
                    "the copy with learners.")
    status = DIFFERENT if other else ACTION if group_only else EXPECTED
    p.add("Release conditions", "Conditions carried over exactly", len(o_sigs), len(o_sigs) - len(lost),
          status, " ".join(note))


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
    if ov == nv:
        note = ""
    elif nv < ov:
        note = "Tests may now draw fewer questions: check them."
    else:
        note = ("More draws in Ultra: question pools or undeployed tests probably became question banks. "
                "Check each test still draws the same number of questions per attempt.")
    p.add("Tests", "Questions drawn through random blocks and question sets", ov, nv,
          SAME if ov == nv else DIFFERENT, note)
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
    elif nt > ot and (extra := _undeployed_questions(p, nrows)) and nt - extra == ot:
        p.add("Tests", "Questions in tests", ot, nt, EXPECTED,
              f"The {extra} extra question(s) are in the Original's undeployed tests, which conversion puts in a "
              "hidden folder (see \"Undeployed tests in a hidden folder\").")
    else:
        p.add("Tests", "Questions in tests", ot, nt, DIFFERENT,
              f"{removed} were of types Ultra removes." if removed else "")


def _undeployed_questions(p: Pair, nrows: list[dict]) -> int:
    """Questions in the copy's tests that came from the Original's undeployed tests (matched by title)."""
    if not p.both("S3b"):
        return 0
    titles = {norm(t.get("title")) for t in undeployed_tests_folder(p)}
    return sum(r.get("questions") or 0 for r in nrows if norm(r.get("test_title")) in titles)


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
        if not p.students_copied and ov and not nv:
            p.add("Learner records", label, ov, nv, EXPECTED,
                  f"Copied without students: this work stays in the Original (Original: {od}).")
            continue
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
    if not p.students_copied and p.orig("S7") and not p.copy("S7"):
        n = len(p.orig("S7"))
        p.add("Learner records", "Grade and attempt records matching", n, 0, EXPECTED,
              f"Copied without students: the {n} record(s) stay in the Original, and are compared when the "
              "course is copied with its learners.")
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

    if not p.students_copied and p.orig("S10") and not p.copy("S10"):
        n = len(p.orig("S10"))
        p.add("SCORM", "SCORM records with the same resume state", n, 0, EXPECTED,
              f"Copied without students: the {n} SCORM record(s) stay in the Original, and are compared when "
              "the course is copied with its learners.")
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


# Totals compared for students whose records aren't read one by one (S2b), with plain names.
_INACTIVE = (("learners", "learners"), ("grade_rows", "grade records"), ("attempts", "attempts"),
             ("open", "attempts in progress"), ("needs_grading", "waiting for grading"),
             ("scorm_registrations", "SCORM records"))


def check_inactive_records(p: Pair):
    """Unavailable and disabled students' records, compared as totals (S2b). They copy too, but by
    default no one's grades or SCORM state is read one by one unless they're in progress."""
    if not p.both("S2b"):
        return

    def totals(rows, state):
        r = next((x for x in rows if x.get("state") == state), {})
        return {k: r.get(k) or 0 for k, _ in _INACTIVE}

    def show(t):
        return f"{t['learners']} learner(s), {t['grade_rows'] + t['scorm_registrations']} record(s)"

    for state, label in (("unavailable", "Unavailable students' records"),
                         ("disabled", "Disabled students' records")):
        a, b = totals(p.orig("S2b"), state), totals(p.copy("S2b"), state)
        if not any(a.values()) and not any(b.values()):
            continue
        now = totals(p.now("S2b"), state) if "S2b_now" in p.ran_post else None
        if not p.students_copied and not any(b.values()):
            p.add("Learner records", label, show(a), show(b), EXPECTED,
                  "Copied without students: their records stay in the Original.")
            continue
        if a == b:
            p.add("Learner records", label, show(a), show(b), SAME,
                  "Compared as totals: grade records, attempts and SCORM records.")
        elif now == b:
            p.add("Learner records", label, show(a), show(b), EXPECTED,
                  "Matches the Original now: learners' access changed after the pre-scan.")
        else:
            off = "; ".join(f"{name} {a[k]} to {b[k]}" for k, name in _INACTIVE if a[k] != b[k])
            p.add("Learner records", label, show(a), show(b), DIFFERENT,
                  f"Totals differ: {off}. To see whose, scan the Original again with every learner "
                  "(pre --all-learners) and post-scan against that.")


def check_hidden_columns(p: Pair):
    """Grade columns hidden in the Original that learners can see in Ultra (S4 through M2): either
    marked visible, or still marked hidden but attached to an item learners can open, which in
    Ultra shows the column too."""
    if not (p.both("S4") and "M2" in p.ran_post):
        return
    copy_cols = {r["col_pk"]: r for r in p.copy("S4")}
    # The attached item's availability: from S4 when the scan has it, else from the copy's tree.
    tree_avail = {r.get("content_pk"): r.get("available_ind") for r in p.copy("S3b")}

    def item_available(col):
        if col.get("content_pk") in (None, ""):
            return None
        return col.get("item_available") or tree_avail.get(col.get("content_pk"))

    shown, follows_item = [], []
    for m in column_map(p.post, p.o).values():
        if m.get("visible_ind") != "N":
            continue
        col = copy_cols.get(m.get("new_col_pk"))
        if not col:
            continue
        if col.get("visible_ind") == "Y":
            shown.append(m["title"])
        elif item_available(col) == "Y":
            follows_item.append(m["title"])   # marked hidden, but Ultra shows it with its item
    if shown:
        p.add("Grades", "Hidden columns now visible", len(shown), len(shown), ACTION,
              "Decide whether to hide, remove or keep: " + _list(shown))
    if follows_item:
        p.add("Grades", "Hidden columns that learners see with their item", len(follows_item), len(follows_item),
              EXPECTED, "Hidden in the Original, but attached to an item learners can open. In Ultra a column shows "
              "whenever its item does, so learners see these scores; they can't be hidden without hiding the item: "
              + _list(follows_item))


CHECKS = (check_copy_task, check_members, check_content_counts, check_content_types, check_nesting,
          check_added_folders, check_availability,
          check_grade_columns, check_groups, check_release_conditions, check_partial_credit,
          check_question_sources, check_question_types, check_test_exceptions, check_work_in_progress,
          check_learner_records, check_scorm, check_inactive_records, check_hidden_columns)


def compare_course(o: str, n: str, base: dict, post: dict, ran_base: set, ran_post: set,
                   labels: dict | None = None, students_copied: bool = True):
    """Return (checks, learner_diffs) for one Original and its copy."""
    p = Pair(o, n, base, post, ran_base, ran_post, labels=labels or {}, students_copied=students_copied)
    if not _one(post, "S1", n):
        p.add("Course", "Copy exists", o, "not found", ACTION, f"No course with the ID {n}.")
        return p.checks, p.diffs
    for check in CHECKS:
        check(p)
    return p.checks, p.diffs


def id_map(o: str, n: str, base: dict, post: dict) -> list[dict]:
    """The course row, every Original column with its match, and columns that exist only in Ultra.
    A course row's IDs are course_main.pk1, with course_main.batch_uid beside them; a grade column
    row's IDs are gradebook_main.pk1, with the attached item's course_contents.pk1 beside them."""
    o_s1, n_s1 = _one(base, "S1", o), _one(post, "S1", n)
    o_pk, n_pk = o_s1.get("crs_pk"), n_s1.get("crs_pk")
    # Grade column pk -> its attached item's content pk, on each side (S4).
    o_item = {str(r["col_pk"]): r.get("content_pk") for r in _rows(base, "S4", o)}
    n_item = {str(r["col_pk"]): r.get("content_pk") for r in _rows(post, "S4", n)}

    def item(side, col_pk):
        v = side.get(str(col_pk)) if col_pk not in (None, "") else None
        return "" if v in (None, "") else v

    def row(**kw):
        r = dict.fromkeys(ID_MAP_COLUMNS, "")
        r.update(orig_course_id=o, new_course_id=n, **kw)
        return r

    def plain(title):
        return re.sub(r"<[^>]*>", "", title or "")

    rows = [row(kind="course", table="course_main", orig_pk1=o_pk or "", new_pk1=n_pk or "",
                title=o_s1.get("course_name", ""),
                orig_batch_uid=o_s1.get("batch_uid") or "", new_batch_uid=n_s1.get("batch_uid") or "",
                match_status="matched" if n_pk else "not found")]
    mapped = set()
    for m in sorted(column_map(post, o).values(), key=lambda r: r["orig_col_pk"]):
        mapped.add(m.get("new_col_pk"))
        status = m.get("match_status", "")
        if status == "not found" and _WEIGHTED.search(m.get("title") or ""):
            status = "removed in Ultra (weighted total)"
        elif status == "not found" and _DEFAULT_TOTAL.search(m.get("title") or ""):
            status = "removed in Ultra (default total, nothing graded)"
        rows.append(row(kind="grade column", table="gradebook_main",
                        orig_pk1=m["orig_col_pk"], new_pk1=m.get("new_col_pk") or "", title=m.get("title", ""),
                        orig_course_contents_pk1=item(o_item, m["orig_col_pk"]),
                        new_course_contents_pk1=item(n_item, m.get("new_col_pk")),
                        attached_item=plain(m.get("content_title")), match_status=status))
    for r in _rows(post, "S4", n):
        if r["col_pk"] not in mapped:
            rows.append(row(kind="grade column", table="gradebook_main", new_pk1=r["col_pk"],
                            title=r.get("title", ""), new_course_contents_pk1=item(n_item, r["col_pk"]),
                            attached_item=plain(r.get("content_title")), match_status="new in Ultra"))
    return rows


# idmap.csv, in this order. Database names throughout: pk1 is the row's numeric primary key in `table`
# (course_main or gradebook_main), as stored in the database and read through DDA.
ID_MAP_COLUMNS = ("orig_course_id", "new_course_id", "kind", "table", "orig_pk1", "new_pk1", "title",
                  "orig_course_contents_pk1", "new_course_contents_pk1", "attached_item",
                  "orig_batch_uid", "new_batch_uid", "match_status")
