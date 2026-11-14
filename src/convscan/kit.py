"""The SQL kit: load the template, expand placeholders, split into labeled statements."""
from __future__ import annotations

import pathlib
import re

from .config import PACKAGE

TEMPLATE = PACKAGE / "sql" / "conversion_scan.template.sql"

# Per-learner queries: large on big courses, skippable with --no-learner.
LEARNER = {"S7", "S7b", "S8b", "S10", "S12b"}

# Re-read from the Originals during the post-scan, saved as <label>_now.
NOW = {"S2", "S7", "S10"}

_LABEL = re.compile(r"^-- ((?:S|M)\d+[a-z]?)\.", re.M)
_COMMENT_ONLY = re.compile(r"^\s*(--.*)?$")


def load_template(path: pathlib.Path | None = None) -> str:
    return (path or TEMPLATE).read_text(encoding="utf-8")


def statements(template: str, scope_sql: str, suffix: str, pairs_sql: str | None = None,
               only: set[str] | None = None, skip: set[str] | None = None) -> list[tuple[str, str]]:
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
        out.append((label, chunk.replace("{SCOPE}", scope_sql).strip()))
    return out


def as_script(stmts: list[tuple[str, str]]) -> str:
    """One file for other tools: each statement ends with a semicolon on its own line."""
    return "\n\n".join(f"-- [{label}]\n{sql}\n;" for label, sql in stmts) + "\n"
