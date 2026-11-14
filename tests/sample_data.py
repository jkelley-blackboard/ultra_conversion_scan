"""Invented scan data for two courses, used by the offline test and to build examples/.

DEMO101 has the known losses: a group that gates content, a partial-credit question, a hidden grade
column that becomes visible, and an open test attempt. DEMO102 is clean. Their copies are
DEMO101-7777 and DEMO102-7777. No real course, learner or site data.

    write_runs(folder) -> (pre_folder, post_folder)
"""
from __future__ import annotations

import csv
import json
import pathlib

PAIRS = [("DEMO101", "DEMO101-7777"), ("DEMO102", "DEMO102-7777")]
LEARNERS = (5001, 5002, 5003)

SETTINGS = [
    {"registry_key": "course.structure.max_level_of_nesting", "registry_value": "3"},
    {"registry_key": "ultraui.converting.content.areas.to.learning.modules", "registry_value": "true"},
    {"registry_key": "ultraui.converting.folder.and.learning.module.descriptions.to.documents", "registry_value": "false"},
    {"registry_key": "ultraui.converting.undeployed.tests.to.question.banks", "registry_value": "false"},
]


def _course(cid, crs_pk, name, suffix_id, taken=False, available="N"):
    return {"course_id": cid, "crs_pk": crs_pk, "course_name": name, "ultra_status": "C",
            "available_ind": available, "row_status": 0, "expected_new_course_id": suffix_id,
            "new_id_length": len(suffix_id), "new_id_taken": "true" if taken else "false"}


def _side(copy: bool) -> dict[str, list[dict]]:
    """One scan: the Originals (copy=False) or the copies (copy=True)."""
    c1, c2 = ("DEMO101-7777", "DEMO102-7777") if copy else ("DEMO101", "DEMO102")
    pk = 900 if copy else 100            # copies get new internal IDs
    col = lambda n: pk * 10 + n          # grade column IDs
    d: dict[str, list[dict]] = {}

    d["S1"] = [_course(c1, pk + 1, "Introduction to Portfolio Management", "DEMO101-7777"),
               _course(c2, pk + 2, "Ethics in Practice", "DEMO102-7777")]
    d["S2"] = [{"course_id": c, "members": 4, "staff": 1, "students": 3, "in_progress": 2, "completed": 1,
                "students_disabled": 0, "ip_lt30d": 2, "ip_gt90d": 0, "ip_never": 0} for c in (c1, c2)]
    d["S3"] = [
        {"course_id": c1, "items": 14 if copy else 10, "scorm": 1, "tests": 2, "assignments": 0, "forum_links": 1,
         "lti_items": 0, "items_unavailable": 1, "cc_references": 0, "cc_html_pages": 0, "dated_items": 0},
        {"course_id": c2, "items": 8 if copy else 6, "scorm": 0, "tests": 1, "assignments": 1 if not copy else 0,
         "forum_links": 0, "lti_items": 0, "items_unavailable": 0, "cc_references": 0, "cc_html_pages": 0,
         "dated_items": 0},
    ]
    if copy:   # conversion turns the assignment into an Ultra assessment
        d["S3"][1]["tests"] = 2
    d["S3c"] = [
        {"course_id": c1, "cnthndlr_handle": "resource/x-bb-folder", "items": 5 if copy else 3, "items_unavailable": 0},
        {"course_id": c1, "cnthndlr_handle": "resource/x-bb-document", "items": 5 if copy else 3, "items_unavailable": 1},
        {"course_id": c1, "cnthndlr_handle": "resource/x-bb-asmt-test-link", "items": 2, "items_unavailable": 0},
        {"course_id": c1, "cnthndlr_handle": "resource/x-plugin-scormengine", "items": 1, "items_unavailable": 0},
        {"course_id": c1, "cnthndlr_handle": "resource/x-bb-forumlink", "items": 1, "items_unavailable": 0},
        {"course_id": c2, "cnthndlr_handle": "resource/x-bb-folder", "items": 4 if copy else 2, "items_unavailable": 0},
        {"course_id": c2, "cnthndlr_handle": "resource/x-bb-document", "items": 2, "items_unavailable": 0},
        {"course_id": c2, "cnthndlr_handle": "resource/x-bb-asmt-test-link", "items": 2 if copy else 1,
         "items_unavailable": 0},
    ]
    if not copy:
        d["S3c"].append({"course_id": c2, "cnthndlr_handle": "resource/x-bb-assignment", "items": 1,
                         "items_unavailable": 0})
    item = lambda c, n, h, t, a="Y", parent="Course Content": {
        "course_id": c, "content_pk": pk * 100 + n, "cnthndlr_handle": h, "title": t, "available_ind": a,
        "depth": 1, "path": f"{parent} / {t}", "parent_title": parent, "web_url": ""}
    d["S3b"] = [item(c1, 1, "resource/x-bb-document", "Welcome"),
                item(c1, 2, "resource/x-bb-asmt-test-link", "Module 1 Quiz"),
                item(c1, 3, "resource/x-bb-asmt-test-link", "Placement Test"),
                item(c1, 4, "resource/x-bb-document", "Advanced Readings"),
                item(c1, 5, "resource/x-bb-document", "Instructor Notes", a="N"),
                item(c1, 6, "resource/x-plugin-scormengine", "<u>Module 1 Interactive</u>" if not copy else
                     "Module 1 Interactive"),
                item(c2, 1, "resource/x-bb-document", "Course Overview"),
                item(c2, 2, "resource/x-bb-asmt-test-link", "Final Test"),
                item(c2, 3, "resource/x-bb-assignment" if not copy else "resource/x-bb-asmt-test-link", "Case Study")]

    gcol = lambda c, n, title, handle, content, vis="Y", calc="N": {
        "course_id": c, "col_pk": col(n), "title": title, "score_provider_handle": handle,
        "content_pk": pk * 100 + n if content else "", "content_title": content, "calculated_ind": calc,
        "visible_ind": vis, "visible_in_book_ind": "Y", "orphan_candidate": "false", "grade_rows": 3}
    d["S4"] = [gcol(c1, 2, "Module 1 Quiz", "resource/x-bb-assessment", "Module 1 Quiz"),
               gcol(c1, 3, "Placement Test", "resource/x-bb-assessment", "Placement Test", vis="Y" if copy else "N"),
               gcol(c1, 6, "Module 1 Interactive", "resource/x-plugin-scormengine", "Module 1 Interactive"),
               gcol(c1, 9, "Total", "", "", calc="C" if copy else "T"),
               gcol(c2, 12, "Final Test", "resource/x-bb-assessment", "Final Test"),
               gcol(c2, 13, "Case Study", "resource/x-bb-assessment" if copy else "resource/x-bb-assignment",
                    "Case Study")]
    if not copy:   # Ultra drops the weighted total
        d["S4"].append(gcol(c1, 8, "Weighted Total", "", "", calc="W"))

    d["S5b"] = [{"course_id": c1, "tests_with_partial_credit": 1, "partial_credit_questions": 1,
                 "from_pools_or_sets": 0, "in_routing_tests": 0, "in_gating_tests": 1, "in_graded_only_tests": 0}]
    d["S5c"] = [{"course_id": c1, "col_pk": col(3), "test_title": "Placement Test", "source": "direct",
                 "question_pk": pk * 1000 + 1, "question_title": "Risk profile", "question_type": "Multiple Choice",
                 "points": 10, "answers": 4, "weights_found": 4, "real_partial": "false" if copy else "true",
                 "weights": "A 100 | B 0 | C 0 | D 0" if copy else "A 100 | B 50 | C 25 | D 0"}]
    d["S5d"] = [{"course_id": c1, "test_title": "Module 1 Quiz", "question_type_code": 3 if copy else 1,
                 "question_type": "Multiple Answer" if copy else "Multiple Choice", "removed_by_conversion": "false",
                 "questions": 5},
                {"course_id": c1, "test_title": "Placement Test", "question_type_code": 3 if copy else 1,
                 "question_type": "Multiple Answer" if copy else "Multiple Choice", "removed_by_conversion": "false",
                 "questions": 1},
                {"course_id": c2, "test_title": "Final Test", "question_type_code": 7, "question_type": "Essay",
                 "removed_by_conversion": "false", "questions": 2}]
    d["S5e"] = [{"course_id": c1, "tests": 2, "pools_and_banks": 0, "other_assessments": 0, "block_draws": 0},
                {"course_id": c2, "tests": 1, "pools_and_banks": 0, "other_assessments": 0, "block_draws": 0}]

    d["S7"] = []
    for c, cols in ((c1, (2, 3, 6)), (c2, (12, 13))):
        for u in LEARNERS:
            for n in cols:
                open_attempt = 1 if (c == c1 and u == 5001 and n == 2) else 0
                d["S7"].append({"course_id": c, "users_pk1": u, "col_pk": col(n), "column_title": "",
                                "score_provider_handle": "resource/x-plugin-scormengine" if n == 6 else
                                ("resource/x-bb-assignment" if n == 13 and not copy else "resource/x-bb-assessment"),
                                "manual_score": "", "exempt_ind": "N", "highest_attempt_score": 80,
                                "attempts": 1, "submitted": 1 - open_attempt, "open": open_attempt,
                                "needs_grading": 1 if (n == 13 and u == 5002) else 0})
    d["S8"] = [{"course_id": c1, "group_pk": pk * 10, "group_name": "Advanced Stream", "members": 1,
                "criteria_using_group": 1, "test_exceptions_using_group": 0}] if not copy else []
    d["S9"] = [{"course_id": c1, "content_pk": pk * 100 + 4, "item_title": "Advanced Readings",
                "parent_title": "Course Content", "cnthndlr_handle": "resource/x-bb-document", "crit_type": "GROUP",
                "negate_ind": "N", "gate_column_title": "", "gate_column_calculated": "", "min_score": "",
                "max_score": "", "start_date": "", "end_date": "", "reviewed_item_title": "",
                "groups_named": "" if copy else "Advanced Stream", "users_named": "", "users_named_count": 0},
               {"course_id": c1, "content_pk": pk * 100 + 2, "item_title": "Module 1 Quiz",
                "parent_title": "Course Content", "cnthndlr_handle": "resource/x-bb-asmt-test-link",
                "crit_type": "GRADE_RANGE_PERCENT", "negate_ind": "N", "gate_column_title": "Placement Test",
                "gate_column_calculated": "N", "min_score": 60, "max_score": 100, "start_date": "", "end_date": "",
                "reviewed_item_title": "", "groups_named": "", "users_named": "", "users_named_count": 0}]
    d["S10"] = [{"course_id": c1, "users_pk1": u, "content_pk": pk * 100 + 6,
                 "scorm_title": "Module 1 Interactive" if copy else "<u>Module 1 Interactive</u>", "attempt_no": 1,
                 "runtime_md5": "", "blob_md5": f"fingerprint-{u}", "blob_scos": 1, "blob_locations": "page4"}
                for u in LEARNERS]
    d["S11"] = [{"course_id": c1, "forums": 1, "posts": 6, "posting_users": 3}]
    d["S12"] = [{"course_id": c1, "col_pk": col(2), "test_title": "Module 1 Quiz", "time_limit_minutes": "",
                 "proctoring_service_handle": "", "req_secure_browser_take_ind": "N",
                 "open_attempts": 1, "learners_with_open_attempt": 1},
                {"course_id": c1, "col_pk": col(3), "test_title": "Placement Test", "time_limit_minutes": 20,
                 "proctoring_service_handle": "", "req_secure_browser_take_ind": "N",
                 "open_attempts": 0, "learners_with_open_attempt": 0},
                {"course_id": c2, "col_pk": col(12), "test_title": "Final Test", "time_limit_minutes": "",
                 "proctoring_service_handle": "", "req_secure_browser_take_ind": "N",
                 "open_attempts": 0, "learners_with_open_attempt": 0}]
    d["S12b"] = []
    d["S14"] = SETTINGS
    if copy:
        d["S13"] = [{"course_id": n, "task_type": "BulkCopyAndConvertOperation", "status": "C",
                     "status_label": "complete", "end_date": "2026-12-01T09:00:00", "seconds": 40,
                     "results_text": "copy|copy.msg.clone.operation.success"} for _, n in PAIRS]
        m2 = lambda o, n, opk, npk, title, content, handle, calc="N", vis="Y", status="matched": {
            "orig_course_id": o, "new_course_id": n, "orig_col_pk": opk, "title": title, "content_title": content,
            "score_provider_handle": handle, "calculated_ind": calc, "visible_ind": vis, "match_status": status,
            "new_col_pk": npk, "match_level": 1 if content else 3, "candidates": npk}
        d["M2"] = [m2("DEMO101", "DEMO101-7777", 1002, 9002, "Module 1 Quiz", "Module 1 Quiz", "resource/x-bb-assessment"),
                   m2("DEMO101", "DEMO101-7777", 1003, 9003, "Placement Test", "Placement Test",
                      "resource/x-bb-assessment", vis="N"),
                   m2("DEMO101", "DEMO101-7777", 1006, 9006, "Module 1 Interactive", "Module 1 Interactive",
                      "resource/x-plugin-scormengine"),
                   m2("DEMO101", "DEMO101-7777", 1008, "", "Weighted Total", "", "", calc="W", status="not found"),
                   m2("DEMO101", "DEMO101-7777", 1009, 9009, "Total", "", "", calc="T"),
                   m2("DEMO102", "DEMO102-7777", 1012, 9012, "Final Test", "Final Test", "resource/x-bb-assessment"),
                   m2("DEMO102", "DEMO102-7777", 1013, 9013, "Case Study", "Case Study", "resource/x-bb-assignment")]
    return d


def _write(folder: pathlib.Path, data: dict[str, list[dict]], meta: dict):
    (folder / "data").mkdir(parents=True, exist_ok=True)
    for label, rows in data.items():
        cols = list(dict.fromkeys(k for r in rows for k in r)) or ["course_id"]
        with open(folder / "data" / f"{label}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)
    queries = {label: {"rows": len(rows), "seconds": 0.0} for label, rows in data.items()}
    (folder / "run.json").write_text(json.dumps({**meta, "convscan": "sample", "queries": queries}, indent=2),
                                     encoding="utf-8")


def write_runs(folder) -> tuple[pathlib.Path, pathlib.Path]:
    folder = pathlib.Path(folder)
    pre, post = folder / "sample_pre", folder / "sample_post"
    common = {"scope": "manifest (2 courses)", "suffix": "-7777", "pairs": [list(p) for p in PAIRS]}
    _write(pre, _side(copy=False), {**common, "mode": "pre", "name": "sample_pre", "finished": "2026-11-30T08:00:00"})
    _write(post, _side(copy=True), {**common, "mode": "post", "name": "sample_post",
                                    "finished": "2026-12-01T10:00:00", "baseline": str(pre.resolve())})
    return pre, post
