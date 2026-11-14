"""Rule table evaluation: query results in, findings out. No judgment lives in code."""
from __future__ import annotations

import pathlib
import re

import yaml

SEVERITY = {
    1: "Blocks learners",
    2: "Needs fixing",
    3: "Improves the experience",
    4: "Ultra opportunity",
    0: "To check",
}
# Order findings in a report: blockers first, "to check" last.
SEVERITY_ORDER = {1: 0, 2: 1, 3: 2, 4: 3, 0: 4}

_MEASURE = re.compile(r"(sum|max|min|any|distinct)\((\w+)\)")


def load_rules(path: pathlib.Path) -> dict:
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    ids = [r["id"] for r in doc["rules"]]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise SystemExit(f"{path}: duplicate rule ids {sorted(dupes)}")
    return doc


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def matches(row: dict, where: dict | None) -> bool:
    for key, want in (where or {}).items():
        col, _, op = key.partition("__")
        v = row.get(col)
        if op == "":
            ok = v in want if isinstance(want, list) else v == want
        elif op == "ne":
            ok = v not in want if isinstance(want, list) else v != want
        elif op in ("gt", "gte", "lt"):
            n = _num(v)
            ok = n is not None and {"gt": n > want, "gte": n >= want, "lt": n < want}[op]
        elif op == "notnull":  # an empty string counts as null (text columns stay strings)
            ok = (v not in (None, "")) == bool(want)
        elif op == "null":
            ok = (v in (None, "")) == bool(want)
        elif op == "contains":
            ok = v is not None and str(want).lower() in str(v).lower()
        elif op == "startswith":
            ok = v is not None and str(v).startswith(str(want))
        else:
            raise ValueError(f"unknown filter operator in {key!r}")
        if not ok:
            return False
    return True


def measure(rows: list[dict], spec: str):
    if spec == "count":
        return len(rows)
    m = _MEASURE.fullmatch(spec)
    if not m:
        raise ValueError(f"unknown measure {spec!r}")
    fn, col = m.groups()
    vals = [r.get(col) for r in rows]
    if fn == "any":
        return sum(1 for v in vals if v)
    if fn == "distinct":
        return len({v for v in vals if v is not None})
    nums = [n for n in map(_num, vals) if n is not None]
    if fn == "sum":
        return sum(nums)
    if not nums:
        return 0
    return max(nums) if fn == "max" else min(nums)


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def evaluate(doc: dict, data: dict[str, list[dict]], course_id: str, ran: set[str],
             cfg: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Return (findings, not_checked) for one course.

    A threshold may be {config: <key>}: the value comes from the config, and 0 switches the rule off.
    """
    findings, not_checked = [], []
    for rule in doc["rules"]:
        threshold = rule.get("threshold", 0)
        if isinstance(threshold, dict):
            threshold = (cfg or {}).get(threshold["config"]) or 0
            if not threshold:
                continue
        src = rule["source"]
        if src not in ran:
            not_checked.append({"id": rule["id"], "title": rule["title"], "reason": f"{src} was not run"})
            continue
        rows = [r for r in data.get(src, []) if r.get("course_id") == course_id and matches(r, rule.get("where"))]
        value = measure(rows, rule.get("measure", "count"))
        if not value > threshold:
            continue
        examples = ""
        if rule.get("examples"):
            seen = []
            for r in rows:
                v = r.get(rule["examples"])
                if v not in (None, "") and v not in seen:
                    seen.append(v)
            examples = "; ".join(map(str, seen[:5])) + (f" (and {len(seen) - 5} more)" if len(seen) > 5 else "")
        fmt = _Safe(value=value, n=len(rows), examples=examples or "none listed", first=rows[0] if rows else {})
        sev = rule["severity"]
        findings.append({
            "id": rule["id"], "title": rule["title"], "severity": sev, "severity_label": SEVERITY[sev],
            "known": rule.get("known", False), "value": value, "n": len(rows),
            "says": rule.get("says", "").format_map(fmt).strip(),
            "action": rule.get("action", "").format_map(fmt).strip(),
            "decision": rule.get("decision", False),
        })
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["id"]))
    return findings, not_checked
