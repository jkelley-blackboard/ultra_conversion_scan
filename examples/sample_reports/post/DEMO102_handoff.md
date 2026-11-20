# Conversion Hand-off Report: DEMO102, Ethics in Practice

**Prepared for:** Sample University | **Post-scan:** 2026-12-01 | **Baseline:** 2026-11-30 | **Batch:** sample_post

> Generated from the LMS reporting database by convscan 0.4.0, by comparing the Ultra copy with the Original as scanned before conversion. Where each value comes from (`table.field`): [REPORT_KEY.md](REPORT_KEY.md).

## Summary

| | |
|---|---|
| Course ID (`course_main.course_id`) | DEMO102 → **DEMO102-7777** (Ultra) |
| External ID (`course_main.batch_uid`) | DEMO102 → DEMO102-7777 |
| Course primary key (`course_main.pk1`) | 102 → 902 |
| Learners | 4 members, 2 in progress |
| Checks | 25 same, 1 expected changes, 0 expected but should fix, 0 different, 0 need action, 0 not checked |
| Status | **Ready to verify and release** |

## Checks

| Area | Check | Original | Ultra copy | Result | Note |
|---|---|---|---|---|---|
| Course | Copy and convert task |  | complete | Same | 2026-12-01T09:00, 40 s. succeeded |
| Members | Active members | 4 | 4 | Same |  |
| Members | Students | 3 | 3 | Same |  |
| Members | Students in progress | 2 | 2 | Same |  |
| Members | Students completed or expired | 1 | 1 | Same |  |
| Members | Disabled students | 0 | 0 | Same |  |
| Content | Tests and assignments | 2 | 2 | Same |  |
| Content | SCORM items | 0 | 0 | Same |  |
| Content | Discussion links | 0 | 0 | Same |  |
| Content | LTI tool links | 0 | 0 | Same |  |
| Content | All items | 6 | 8 | Expected | Conversion adds folders. |
| Content | Content types carried over | 3 | 3 | Same | Added by conversion: Folder +2. |
| Content | Hidden items still hidden | 0 | 0 | Same |  |
| Grades | Grade columns | 2 | 2 | Same |  |
| Groups | Groups | 0 | 0 | Same |  |
| Release conditions | Gated items still gated | 0 | 0 | Same |  |
| Release conditions | Conditions carried over exactly | 0 | 0 | Same | Same item, type, score range, dates, gate column, groups and named learners. |
| Tests | Questions with partial-credit answer values | 0 | 0 | Same |  |
| Tests | Questions drawn through random blocks and question sets | 0 | 0 | Same |  |
| Tests | Questions in tests | 2 | 2 | Same |  |
| Tests | Test exceptions | 0 | 0 | Same |  |
| Learner records | Attempts in progress | 0 | 0 | Same |  |
| Learner records | Submissions waiting for grading | 1 | 1 | Same | Original: 1 assignments. Ultra: 1 tests. (Assignments convert to Ultra assessments, so the split by type changes.) |
| Learner records | Grade and attempt records matching | 4 | 4 | Same |  |
| SCORM | SCORM records with the same resume state | 0 | 0 | Same | No SCORM records in this course. |
| Learner records | Unavailable students' records | 1 learner(s), 2 record(s) | 1 learner(s), 2 record(s) | Same | Compared as totals: grade records, attempts and SCORM records. |

## ID map

Every grade column in the Original, matched to the Ultra copy by its attached item. The full map for the batch is in `idmap.csv`, with the same columns. IDs are the numeric primary keys as stored in the database: `pk1` is `course_main.pk1` on the course row and `gradebook_main.pk1` on a grade column row; `course_contents_pk1` is `gradebook_main.course_contents_pk1`, the item the column belongs to.

| `table` | `orig_pk1` | `new_pk1` | `title` | `attached_item` | `orig_course_contents_pk1` | `new_course_contents_pk1` | `match_status` |
|---|---|---|---|---|---|---|---|
| course_main | 102 | 902 | Ethics in Practice |  |  |  | matched |
| gradebook_main | 1012 | 9012 | Final Test | Final Test | 10012 | 90012 | matched |
| gradebook_main | 1013 | 9013 | Case Study | Case Study | 10013 | 90013 | matched |

Grade columns by match: matched 2. An ambiguous or not-found column is resolved before hand-off; columns new in Ultra can be ignored.

## Site conversion settings at the post-scan

| Setting | This site |
|---|---|
| Blackboard LMS version | 4001.7.0-rel.4+a1cda0a |
| Content takes the release conditions of its folder or learning module | Yes |
| Levels of nested content (3 by default, 4 with the additional level) | 3 |
| Content areas become learning modules | Yes |
| Folder and learning module descriptions become documents | No |
| Undeployed tests become question banks | Yes |

## Not checked by this scan

- What a learner sees on screen, and whether SCORM content resumes in the player.
- Whether files linked from the Content Collection still open.
- Systems outside the LMS that store course or grade column IDs: update them from the ID map.
- Each record of students who were unavailable or disabled at the pre-scan: their records are compared as totals, not one by one.
