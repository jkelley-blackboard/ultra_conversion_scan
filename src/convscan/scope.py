"""Scope SQL: which courses a scan covers, from a manifest or an institutional hierarchy node.

A scope is a SELECT returning (crs_pk, course_id, course_name). Pairs (for M2) are a SELECT
returning (orig_course_id, new_course_id).
"""
from __future__ import annotations

import csv
from dataclasses import dataclass


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _in_list(ids: list[str]) -> str:
    return ",\n      ".join(", ".join(_q(i) for i in ids[n:n + 12]) for n in range(0, len(ids), 12))


def _scope_where(ids_sql: str) -> str:
    return ("\n  select cm.pk1 as crs_pk, cm.course_id, cm.course_name\n  from course_main cm\n"
            f"  where cm.course_id in (\n    {ids_sql})\n")


def node_members_sql(uid: str) -> str:
    """Original course_ids associated with the node (primary or secondary association)."""
    return ("select distinct cm.course_id from course_main cm\n"
            "    join domain_course_coll dcc on dcc.course_main_pk1 = cm.pk1\n"
            f"    join mi_node n on n.domain_pk1 = dcc.domain_pk1 and n.batch_uid = {_q(uid)}")


@dataclass
class Scope:
    """Either a manifest (list of pairs) or a node batch_uid."""
    pairs: list[tuple[str, str]] | None = None
    node: str | None = None
    suffix: str = "-7777"
    prefix: str = ""

    def new_id(self, orig: str) -> str:
        """The copy's course_id by the naming rule: prefix + Original course_id + suffix."""
        return self.prefix + orig + self.suffix

    def _new_id_sql(self, col: str) -> str:
        return f"{_q(self.prefix)} || {col} || {_q(self.suffix)}"

    @classmethod
    def from_manifest(cls, path: str, suffix: str, prefix: str = "") -> "Scope":
        with open(path, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        pairs = []
        for r in rows:
            orig = (r.get("orig_course_id") or "").strip()
            if not orig:
                continue
            new = (r.get("new_course_id") or "").strip() or prefix + orig + suffix
            pairs.append((orig, new))
        if not pairs:
            raise SystemExit(f"{path}: no orig_course_id values")
        return cls(pairs=pairs, suffix=suffix, prefix=prefix)

    @classmethod
    def from_node(cls, uid: str, suffix: str, prefix: str = "") -> "Scope":
        return cls(node=uid, suffix=suffix, prefix=prefix)

    def describe(self) -> str:
        return f"node {self.node}" if self.node else f"manifest ({len(self.pairs)} courses)"

    def originals_sql(self) -> str:
        if self.node:
            return _scope_where(node_members_sql(self.node))
        return _scope_where(_in_list([o for o, _ in self.pairs]))

    def copies_sql(self) -> str:
        if self.node:
            return _scope_where(f"select {self._new_id_sql('o.course_id')} from (\n    "
                                f"{node_members_sql(self.node)}) o")
        return _scope_where(_in_list([n for _, n in self.pairs]))

    def pairs_sql(self) -> str:
        if self.node:
            return (f"\n  select o.course_id as orig_course_id, {self._new_id_sql('o.course_id')} as new_course_id"
                    f" from (\n    {node_members_sql(self.node)}) o\n")
        rows = ",\n    ".join(f"({_q(o)}, {_q(n)})" for o, n in self.pairs)
        return f"\n  select * from (values\n    {rows}) as v(orig_course_id, new_course_id)\n"
