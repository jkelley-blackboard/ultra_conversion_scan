"""The SQL kit: load the template, expand placeholders, split into labeled statements."""
from __future__ import annotations

import pathlib
import re

from .config import PACKAGE

TEMPLATE = PACKAGE / "sql" / "conversion_scan.template.sql"

# Per-learner queries: large on big courses, skippable with --no-learner.
LEARNER = {"S7", "S8b", "S10", "S12b"}

# Re-read from the Originals during the post-scan, saved as <label>_now.
NOW = {"S2", "S2b", "S7", "S10"}

# The {LEARNERS} filter in S7, S8b and S10. By default only students in progress (available) are read
# one by one; unavailable and disabled students are totalled in S2b. ALL_LEARNERS reads every enabled
# student (pre --all-learners).
ACTIVE_LEARNERS = "and cu.available_ind = 'Y'"
ALL_LEARNERS = ""


def learner_filter(run: dict, data: dict, pairs: list) -> str:
    """The post-scan's filter: in each course, the learners its baseline read, not their state now.

    A learner whose access ends (or is extended) between the scans is still compared. Each pair's
    Original and copy get the Original's learners, course by course, so a learner in progress in one
    course of the batch isn't read in another where they're inactive. A baseline made before the
    default changed, or with --all-learners, read everyone, so the post-scan does too.
    """
    if run.get("learners", "all") == "all":
        return ALL_LEARNERS
    copies = {}
    for o, n in pairs:
        copies.setdefault(o, set()).update({o, n})
    rows = sorted({(cid, int(r["users_pk1"])) for label in ("S7", "S8b", "S10") for r in data.get(label, [])
                   if r.get("users_pk1") not in (None, "") for cid in copies.get(r["course_id"], ())})
    if not rows:
        return "and false"
    values = ", ".join("('" + c.replace("'", "''") + f"', {u})" for c, u in rows)
    return ("and (cu.crsmain_pk1, cu.users_pk1) in (select lf_cm.pk1, lf.u from (values " + values
            + ") as lf(c, u) join course_main lf_cm on lf_cm.course_id = lf.c)")

_LABEL = re.compile(r"^-- ((?:S|M)\d+[a-z]?)\.", re.M)
_COMMENT_ONLY = re.compile(r"^\s*(--.*)?$")


def load_template(path: pathlib.Path | None = None) -> str:
    return (path or TEMPLATE).read_text(encoding="utf-8")


def statements(template: str, scope_sql: str, suffix: str, pairs_sql: str | None = None,
               only: set[str] | None = None, skip: set[str] | None = None,
               learners: str = ACTIVE_LEARNERS) -> list[tuple[str, str]]:
    """Return [(label, sql)] in template order.

    Statements are separated by a semicolon at the end of a line (comment lines in the template
    must never end in one). Each statement takes the last "-- S<n>." or "-- M<n>." label in its
    chunk. M2 needs pairs_sql and is left out without it.
    """
    out = []
    for chunk in re.split(r";\s*\n", template.replace("{SUFFIX}", suffix.replace("'", "''"))):
        labels = _LABEL.findall(chunk)
        if not labels or all(_COMMENT_ONLY.match(line) for line in chunk.splitlines()):
            continue
        label = labels[-1]
        if (only and label not in only) or (skip and label in skip):
            continue
        if "{PAIRS}" in chunk:
            if pairs_sql is None:
                continue
            chunk = chunk.replace("{PAIRS}", pairs_sql)
        out.append((label, chunk.replace("{LEARNERS}", learners).replace("{SCOPE}", scope_sql).strip()))
    return out


def as_script(stmts: list[tuple[str, str]]) -> str:
    """One file for other tools: each statement ends with a semicolon on its own line."""
    return "\n\n".join(f"-- [{label}]\n{sql}\n;" for label, sql in stmts) + "\n"
