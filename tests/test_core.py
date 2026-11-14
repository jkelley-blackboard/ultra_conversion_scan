"""Offline tests: kit splitting, scope SQL, rule evaluation. No database needed."""
from convscan import config, kit, rules
from convscan.scope import Scope

EXPECTED = ["S0", "S1", "S2", "S3", "S3b", "S4", "S5", "S5b", "S5c", "S6", "S7", "S7b", "S8", "S8b",
            "S9", "S10", "S11", "S12", "S12b", "M2"]


def test_kit_splits_into_every_labeled_statement():
    stmts = kit.statements(kit.load_template(), "select 1", "7777", pairs_sql="select 1")
    assert [label for label, _ in stmts] == EXPECTED


def test_placeholders_all_replaced():
    for label, sql in kit.statements(kit.load_template(), "SCOPE_X", "7777", pairs_sql="PAIRS_X"):
        assert "{SCOPE}" not in sql and "{PAIRS}" not in sql and "{SUFFIX}" not in sql, label


def test_m2_left_out_without_pairs_and_learner_skip():
    labels = [label for label, _ in kit.statements(kit.load_template(), "select 1", "7777", skip=kit.LEARNER)]
    assert "M2" not in labels and not (set(labels) & kit.LEARNER)


def test_suffix_in_s1():
    sql = dict(kit.statements(kit.load_template(), "select 1", "_U"))["S1"]
    assert "|| '_U'" in sql


def test_manifest_defaults_new_id(tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("orig_course_id,new_course_id\nA1,\nB2,B2_NEW\n", encoding="utf-8")
    s = Scope.from_manifest(str(f), "7777")
    assert s.pairs == [("A1", "A17777"), ("B2", "B2_NEW")]
    assert "'A1', 'B2'" in s.originals_sql()
    assert "('B2', 'B2_NEW')" in s.pairs_sql()


def test_node_scope_quotes_uid():
    s = Scope.from_node("cohort'2", "7777")
    assert "'cohort''2'" in s.originals_sql()
    assert "|| '7777'" in s.copies_sql()


def test_default_rules_load_and_reference_real_queries():
    doc = rules.load_rules(config.load(None)["rules"])
    for r in doc["rules"]:
        assert r["source"] in EXPECTED, r["id"]
        assert r["severity"] in rules.SEVERITY, r["id"]
        assert "—" not in r.get("says", "") + r.get("action", ""), r["id"]


def test_rule_evaluation():
    doc = {"rules": [
        {"id": "a", "title": "Open", "source": "S12", "measure": "sum(open_attempts)", "severity": 1,
         "examples": "test_title", "says": "{value} open in {n}: {examples}", "action": "x"},
        {"id": "b", "title": "Hidden", "source": "S4", "where": {"visible_ind": "N"}, "severity": 2, "says": "{n}"},
        {"id": "c", "title": "Skipped", "source": "S7", "severity": 0},
    ]}
    data = {"S12": [{"course_id": "C1", "test_title": "T1", "open_attempts": 2},
                    {"course_id": "C1", "test_title": "T2", "open_attempts": 0},
                    {"course_id": "C2", "test_title": "T9", "open_attempts": 5}],
            "S4": [{"course_id": "C1", "visible_ind": "Y"}]}
    findings, not_checked = rules.evaluate(doc, data, "C1", {"S12", "S4"})
    assert [f["id"] for f in findings] == ["a"]
    assert findings[0]["says"] == "2 open in 2: T1; T2"
    assert [n["id"] for n in not_checked] == ["c"]


def test_filters():
    row = {"a": 3, "b": None, "c": "resource/x-bb-forumlink"}
    assert rules.matches(row, {"a__gt": 2, "b__null": True, "c__startswith": "resource/"})
    assert not rules.matches(row, {"a__lt": 3})
    assert rules.matches(row, {"b__ne": ["N"]}) and not rules.matches(row, {"b__ne": ["N", None]})
