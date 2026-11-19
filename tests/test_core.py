"""Offline tests: kit splitting, scope SQL, rule evaluation. No database needed."""
from convscan import config, kit, rules
from convscan.scope import Scope

EXPECTED = ["S0", "S1", "S2", "S2b", "S3", "S3c", "S3b", "S3d", "S3e", "S4", "S5b", "S5c", "S5d", "S5e", "S5f", "S6", "S7",
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


def _pair(base, post, **kw):
    from convscan.compare import Pair
    labels = set(base) | set(post)
    return Pair("C1", "U-C1", base, post, labels, labels, **kw)


def _status(p, check):
    return next(c for c in p.checks if c["check"] == check)


def test_grade_columns_default_totals_dropped_when_nothing_graded():
    from convscan.compare import EXPECTED, check_grade_columns
    base = {"S4": [{"course_id": "C1", "title": "OutcomeDefinition.Total.title"},
                   {"course_id": "C1", "title": "OutcomeDefinition.WeightedTotal.title"}]}
    p = _pair(base, {"S4": []})
    check_grade_columns(p)
    assert _status(p, "Grade columns")["status"] == EXPECTED


def test_members_copied_without_students():
    from convscan.compare import DIFFERENT, EXPECTED, check_members
    base = {"S2": [{"course_id": "C1", "members": 120, "students": 100, "in_progress": 60, "completed": 40}]}
    post = {"S2": [{"course_id": "U-C1", "members": 20, "students": 0, "in_progress": 0, "completed": 0}]}
    p = _pair(base, post, students_copied=False)
    check_members(p)
    assert all(c["status"] == EXPECTED for c in p.checks if c["original"] != c["ultra"])
    p = _pair(base, post)   # students expected to copy: the same counts are losses
    check_members(p)
    assert _status(p, "Students")["status"] == DIFFERENT


def test_learner_rows_copied_without_students():
    from convscan.compare import (DIFFERENT, EXPECTED, check_learner_records, check_scorm,
                                  check_work_in_progress)
    base = {"S7": [{"course_id": "C1", "users_pk1": 1, "col_pk": 10, "open": 1, "needs_grading": 0,
                    "score_provider_handle": "resource/x-bb-assessment"}],
            "S10": [{"course_id": "C1", "users_pk1": 1, "scorm_title": "Unit 1", "attempt_no": 1}]}
    post = {"S7": [], "S10": [], "M2": []}
    p = _pair(base, post, students_copied=False)
    for check in (check_work_in_progress, check_learner_records, check_scorm):
        check(p)
    assert {c["check"]: c["status"] for c in p.checks} == {
        "Attempts in progress": EXPECTED, "Submissions waiting for grading": "same",
        "Grade and attempt records matching": EXPECTED, "SCORM records with the same resume state": EXPECTED}
    assert not p.diffs
    p = _pair(base, post)   # students expected to copy: the same empty copy is a loss
    check_learner_records(p)
    assert _status(p, "Grade and attempt records matching")["status"] == DIFFERENT


def test_question_draw_note_follows_direction():
    from convscan.compare import check_question_sources
    base = {"S5e": [{"course_id": "C1", "block_draws": 0}]}
    p = _pair(base, {"S5e": [{"course_id": "U-C1", "block_draws": 240}]})
    check_question_sources(p)
    assert "More draws" in p.checks[0]["note"]


def test_nesting_folder_found_higher_with_contents():
    from convscan.compare import DIFFERENT, EXPECTED_FIX, check_nesting
    F, L = "resource/x-bb-folder", "resource/x-bb-forumlink"
    deep = "Content / Unit 1 / Readings"   # a folder in a folder in a content area: level 3 of 3
    row = lambda c, pk, parent, title, path, depth, h: {"course_id": c, "content_pk": pk, "parent_pk": parent,
                                                         "title": title, "path": path, "depth": depth,
                                                         "cnthndlr_handle": h}
    base = {"S3d": [{"course_id": "C1", "content_pk": 3, "title": "Readings", "path": deep, "ultra_level": 3,
                     "max_level": 3}],
            "S3b": [row("C1", 3, 2, "Readings", deep, 2, F),
                    row("C1", 4, 3, "Ch 1", deep + " / Ch 1", 3, L), row("C1", 5, 3, "Ch 2", deep + " / Ch 2", 3, L)]}
    # The copy has another folder at the same path (as when a moved folder lands beside a namesake):
    # matching by parent ID keeps their items apart.
    moved = "ROOT / Content / Readings"
    post = {"S3b": [row("U-C1", 93, 91, "Readings", moved, 2, F),
                    row("U-C1", 94, 93, "Ch 1", moved + " / Ch 1", 3, L),
                    row("U-C1", 95, 93, "Ch 2", moved + " / Ch 2", 3, L),
                    row("U-C1", 96, 91, "Readings", moved, 2, F),
                    row("U-C1", 97, 96, "Other", moved + " / Other", 3, L)]}
    p = _pair(base, post)
    check_nesting(p)
    c = _status(p, "Folders moved up by conversion")
    assert c["status"] == EXPECTED_FIX and "doesn't block release" in c["note"]
    assert c["details"][0]["ultra_path"] == "Content / Readings" and c["details"][0]["ultra_level"] == 2
    assert c["details"][0]["items_ultra"] == 2
    post["S3b"] = post["S3b"][:2]      # one item lost on the way
    p = _pair(base, post)
    check_nesting(p)
    assert _status(p, "Folders moved up by conversion")["status"] == DIFFERENT


def test_folders_added_by_conversion_should_be_fixed():
    from convscan.compare import EXPECTED, EXPECTED_FIX, check_added_folders, check_grade_columns
    F, D, T = "resource/x-bb-folder", "resource/x-bb-document", "resource/x-bb-asmt-test-link"
    row = lambda c, pk, parent, title, depth, h, avail="Y": {"course_id": c, "content_pk": pk, "parent_pk": parent,
                                                             "title": title, "depth": depth, "cnthndlr_handle": h,
                                                             "available_ind": avail}
    base = {"S3b": [row("C1", 1, 0, "Unit 1", 1, F), row("C1", 2, 1, "Note", 2, "resource/x-bb-blankpage")],
            "S4": [{"course_id": "C1", "title": "Quiz"}]}
    post = {"S3b": [row("U-C1", 11, 10, "Unit 1", 1, F), row("U-C1", 12, 11, "Note", 2, F),
                    row("U-C1", 13, 12, "Note", 3, D),
                    row("U-C1", 20, 10, "Undeployed Tests", 1, F, "N"),
                    row("U-C1", 21, 20, "All Questions", 2, T), row("U-C1", 22, 20, "All Questions", 2, T)],
            "S4": [{"course_id": "U-C1", "title": "Quiz", "content_pk": 30},
                   {"course_id": "U-C1", "title": "Pool 1", "content_pk": 21},
                   {"course_id": "U-C1", "title": "Pool 2", "content_pk": 22}]}
    p = _pair(base, post)
    check_added_folders(p)
    check_grade_columns(p)
    got = {c["check"]: c for c in p.checks}
    assert got["Undeployed tests in a hidden folder"]["status"] == EXPECTED_FIX
    assert got["Undeployed tests in a hidden folder"]["ultra"] == 2
    assert got["Items wrapped in a folder by conversion"]["status"] == EXPECTED_FIX
    assert got["Grade columns"]["status"] == EXPECTED_FIX and got["Grade columns"]["note"].startswith("2 column(s)")
    post["S3b"] = post["S3b"][:3]       # no undeployed-tests folder: extra columns are plain Expected
    p = _pair(base, post)
    check_added_folders(p)
    check_grade_columns(p)
    assert _status(p, "Grade columns")["status"] == EXPECTED
    assert "Undeployed tests in a hidden folder" not in {c["check"] for c in p.checks}


def test_undeployed_tests_rule_follows_the_bank_setting():
    from convscan.config import PACKAGE
    doc = rules.load_rules(PACKAGE / "rules" / "default.yaml")
    rows = [{"course_id": "C1", "becomes_bank": False, "drawing_tests": 0}] * 3
    fired = lambda data: {f["id"] for f in rules.evaluate(doc, {"S5f": data}, "C1", {"S5f"}, {})[0]}
    assert "undeployed_tests_hidden_folder" in fired(rows)
    assert "undeployed_tests_hidden_folder" not in fired([dict(r, becomes_bank=True) for r in rows])


def test_description_rules_follow_the_setting():
    from convscan.config import PACKAGE
    doc = rules.load_rules(PACKAGE / "rules" / "default.yaml")
    fired = lambda data: {f["id"]: f["severity"] for f in rules.evaluate(doc, {"S3e": data}, "C1", {"S3e"}, {})[0]}
    row = {"course_id": "C1", "label": "Unit 1", "has_formatting": True, "has_links": True}
    on = fired([dict(row, becomes_document=True, loses_content=False, loses_formatting=False)])
    off = fired([dict(row, becomes_document=False, loses_content=True, loses_formatting=True)])
    assert on == {"descriptions_become_documents": 3}
    assert off == {"descriptions_lose_content": 2, "descriptions_lose_formatting": 3}


def test_hidden_items_and_wrapped_items():
    from convscan.config import PACKAGE
    doc = rules.load_rules(PACKAGE / "rules" / "default.yaml")
    data = {"S3b": [{"course_id": "C1", "title": "Staff note", "available_ind": "N"}],
            "S3c": [{"course_id": "C1", "cnthndlr_handle": "resource/x-bb-document", "items": 4}]}
    got = {f["id"]: f for f in rules.evaluate(doc, data, "C1", {"S3b", "S3c"}, {})[0]}
    assert got["hidden_items"]["severity"] == 0 and "Staff note" in got["hidden_items"]["says"]
    assert got["documents_wrapped"]["severity"] == 3 and "scriptable" not in got["documents_wrapped"]["action"]


def test_hidden_column_rules_split_by_item():
    from convscan.config import PACKAGE
    doc = rules.load_rules(PACKAGE / "rules" / "default.yaml")
    s4 = [{"course_id": "C1", "title": "Quiz 1", "visible_ind": "N", "content_pk": 5, "item_available": "Y"},
          {"course_id": "C1", "title": "Total", "visible_ind": "N", "content_pk": "", "item_available": ""},
          {"course_id": "C1", "title": "Staff test", "visible_ind": "N", "content_pk": 6, "item_available": "N"}]
    got = {f["id"]: f for f in rules.evaluate(doc, {"S4": s4}, "C1", {"S4"}, {})[0]}
    assert got["hidden_columns_shown"]["n"] == 1 and "Quiz 1" in got["hidden_columns_shown"]["says"]
    assert got["hidden_columns_no_item"]["n"] == 1 and "Total" in got["hidden_columns_no_item"]["says"]


def test_hidden_column_follows_its_item_in_the_copy():
    from convscan.compare import ACTION, EXPECTED, check_hidden_columns
    post = {"M2": [{"orig_course_id": "C1", "orig_col_pk": 1, "new_col_pk": 11, "title": "Quiz 1", "visible_ind": "N"},
                   {"orig_course_id": "C1", "orig_col_pk": 2, "new_col_pk": 12, "title": "Total", "visible_ind": "N"},
                   {"orig_course_id": "C1", "orig_col_pk": 3, "new_col_pk": 13, "title": "Old", "visible_ind": "N"}],
            "S4": [{"course_id": "U-C1", "col_pk": 11, "visible_ind": "N", "content_pk": 50, "item_available": "Y"},
                   {"course_id": "U-C1", "col_pk": 12, "visible_ind": "N", "content_pk": None},
                   {"course_id": "U-C1", "col_pk": 13, "visible_ind": "Y", "content_pk": None}]}
    p = _pair({"S4": []}, post)
    check_hidden_columns(p)
    got = {c["check"]: c for c in p.checks}
    assert got["Hidden columns that learners see with their item"]["status"] == EXPECTED
    assert "Quiz 1" in got["Hidden columns that learners see with their item"]["note"]
    assert got["Hidden columns now visible"]["status"] == ACTION and "Old" in got["Hidden columns now visible"]["note"]


def test_sums_placeholder_in_rule_text():
    doc = {"rules": [{"id": "r", "title": "t", "source": "S3d", "severity": 2,
                      "says": "{n} folder(s) holding {sums[items_below]} item(s)"}]}
    rows = [{"course_id": "C1", "items_below": 12}, {"course_id": "C1", "items_below": 3}]
    findings, _ = rules.evaluate(doc, {"S3d": rows}, "C1", {"S3d"})
    assert findings[0]["says"] == "2 folder(s) holding 15 item(s)"


def test_extra_text_follows_its_config_setting():
    doc = {"rules": [{"id": "r", "title": "t", "source": "S3d", "severity": 2, "says": "Base.",
                      "extra": {"config": "nesting_what_if", "says": "What if.", "decision": True}}]}
    data = {"S3d": [{"course_id": "C1"}]}
    on, _ = rules.evaluate(doc, data, "C1", {"S3d"}, {"nesting_what_if": True})
    off, _ = rules.evaluate(doc, data, "C1", {"S3d"}, {"nesting_what_if": False})
    assert on[0]["says"] == "Base. What if." and on[0]["decision"]
    assert off[0]["says"] == "Base." and not off[0]["decision"]


def test_dropped_link_types_named():
    from convscan.compare import check_content_types
    base = {"S3c": [{"course_id": "C1", "cnthndlr_handle": "resource/x-bb-toollink", "items": 2}]}
    p = _pair(base, {"S3c": []}, labels={"resource/x-bb-toollink": "Tool link"})
    check_content_types(p)
    assert "Known loss: conversion drops tool links" in p.checks[0]["note"]
