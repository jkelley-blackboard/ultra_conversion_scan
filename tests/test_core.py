"""Offline tests: kit splitting, scope SQL, rule evaluation. No database needed."""
from convscan import config, kit, rules
from convscan.scope import Scope

EXPECTED = ["S0", "S1", "S2", "S2b", "S3", "S3c", "S3b", "S3d", "S4", "S5b", "S5c", "S5d", "S5e", "S5f", "S6", "S7",
            "S8", "S8b", "S9", "S10", "S11", "S12", "S12b", "S13", "S14", "M2"]


def test_kit_splits_into_every_labeled_statement():
    stmts = kit.statements(kit.load_template(), "select 1", "7777", pairs_sql="select 1")
    assert [label for label, _ in stmts] == EXPECTED


def test_no_comment_line_ends_in_semicolon():
    """The splitter cuts on a semicolon at the end of a line, so a comment ending in one breaks the kit."""
    bad = [n for n, line in enumerate(kit.load_template().splitlines(), 1)
           if line.lstrip().startswith("--") and line.rstrip().endswith(";")]
    assert not bad, f"comment lines ending in ';': {bad}"


def test_placeholders_all_replaced():
    for label, sql in kit.statements(kit.load_template(), "SCOPE_X", "7777", pairs_sql="PAIRS_X"):
        assert "{SCOPE}" not in sql and "{PAIRS}" not in sql and "{SUFFIX}" not in sql, label
        assert "{LEARNERS}" not in sql, label


def test_learner_filter_defaults_to_students_in_progress():
    by_label = dict(kit.statements(kit.load_template(), "select 1", "7777"))
    for label in ("S7", "S8b", "S10"):
        assert "cu.available_ind = 'Y'" in by_label[label], label
    everyone = dict(kit.statements(kit.load_template(), "select 1", "7777", learners=kit.ALL_LEARNERS))
    assert "cu.available_ind = 'Y'" not in everyone["S7"]


def test_post_scan_reads_the_learners_its_baseline_read():
    data = {"S7": [{"course_id": "A", "users_pk1": 5002}, {"course_id": "B", "users_pk1": 5001}],
            "S10": [{"course_id": "A", "users_pk1": 5002}], "S8b": []}
    pairs = [("A", "A-7777"), ("B", "B-7777")]
    filt = kit.learner_filter({"learners": "active"}, data, pairs)
    # Course by course, on the Original and its copy: 5001 isn't read in A, nor 5002 in B.
    assert "('A', 5002), ('A-7777', 5002), ('B', 5001), ('B-7777', 5001)) as lf(c, u)" in filt
    assert kit.learner_filter({}, data, pairs) == ""             # an older baseline read everyone
    assert kit.learner_filter({"learners": "all"}, data, pairs) == ""
    assert kit.learner_filter({"learners": "active"}, {}, pairs) == "and false"


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


def test_prefix_in_s1():
    sql = dict(kit.statements(kit.load_template(), "select 1", "", prefix="ULTRA-"))["S1"]
    assert "'ULTRA-' || s.course_id || ''" in sql
    assert "{PREFIX}" not in sql


def test_no_prefix_by_default():
    sql = dict(kit.statements(kit.load_template(), "select 1", "-7777"))["S1"]
    assert "'' || s.course_id || '-7777'" in sql


def test_manifest_prefix(tmp_path):
    f = tmp_path / "m.csv"
    f.write_text("orig_course_id,new_course_id\nECON101,\nHIST200,HIST200_KEEP\n", encoding="utf-8")
    s = Scope.from_manifest(str(f), "", "ULTRA-")
    assert s.pairs == [("ECON101", "ULTRA-ECON101"), ("HIST200", "HIST200_KEEP")]
    assert s.new_id("BIO150") == "ULTRA-BIO150"


def test_node_scope_prefix():
    s = Scope.from_node("wave1", "", "W1-")
    assert "'W1-' || o.course_id || ''" in s.copies_sql()
    assert "'W1-' || o.course_id || '' as new_course_id" in s.pairs_sql()


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


def _blob(reg_id, location):
    import struct
    import zlib
    xml = (f'<RunTimeData RegistrationId="{reg_id}"><Activity ItemIdentifier="sco1" ActivityAttemptCount="1" dbid="0">'
           f'<ActivityRunTime ActivityId="1" Location="{location}" SuspendData="abc" CompletionStatus="1" '
           f'ScoreRaw="85"></ActivityRunTime></Activity></RunTimeData>').encode()
    return struct.pack("<I", len(xml)) + zlib.compress(xml)


def test_scorm_blob_fingerprint_ignores_identity_but_not_state():
    from convscan.scorm import summarize
    a, b, c = summarize(_blob("reg-A", "page5")), summarize(_blob("reg-B", "page5")), summarize(_blob("reg-A", "page3"))
    assert a["blob_md5"] == b["blob_md5"]          # a copy has a new registration id: same state
    assert a["blob_md5"] != c["blob_md5"]          # a different bookmark is a different state
    assert a["blob_locations"] == "page5" and a["blob_scos"] == 1
    assert summarize(None)["blob_md5"] == ""


def test_filters():
    row = {"a": 3, "b": None, "c": "resource/x-bb-forumlink"}
    assert rules.matches(row, {"a__gt": 2, "b__null": True, "c__startswith": "resource/"})
    assert not rules.matches(row, {"a__lt": 3})
    assert rules.matches(row, {"b__ne": ["N"]}) and not rules.matches(row, {"b__ne": ["N", None]})
