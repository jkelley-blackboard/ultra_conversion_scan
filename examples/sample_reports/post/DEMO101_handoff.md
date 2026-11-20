# Conversion Hand-off Report: DEMO101, Introduction to Portfolio Management

**Prepared for:** Sample University | **Post-scan:** 2026-12-01 10:00 (UTC-05:00) | **Baseline:** 2026-11-30 08:00 (UTC-05:00) | **Batch:** sample_post

> Generated from the LMS reporting database by convscan 0.4.1, by comparing the Ultra copy with the Original as scanned before conversion. Where each value comes from (`table.field`): [REPORT_KEY.md](REPORT_KEY.md).

## Summary

| | |
|---|---|
| Course ID (`course_main.course_id`) | DEMO101 → **DEMO101-7777** (Ultra) |
| External ID (`course_main.batch_uid`) | DEMO101 → DEMO101-7777 |
| Course primary key (`course_main.pk1`) | 101 → 901 |
| Learners | 4 members, 2 in progress |
| Checks | 21 same, 3 expected changes, 1 expected but should fix, 0 different, 4 need action, 0 not checked |
| Status | **4 item(s) need action before release**; 1 item(s) to fix after release, which don't hold it up |

## Needs action before release

- **Groups in use:** Not carried over: Advanced Stream. Run the group repair, then re-scan.
- **Conditions carried over exactly:** 1 lost only their group(s), on: Advanced Readings. The group repair should restore these.
- **Questions with partial-credit answer values:** 1 question(s) lost their answer values: run the partial-credit repair, then re-scan.
- **Hidden columns now visible:** Decide whether to hide, remove or keep: Placement Test

## Expected, should fix: not blockers

Conversion always makes these changes, and learners lose nothing through them: every item is still there and still reachable, so they don't hold up release. They should still be put right after the course opens, so the Ultra course reads the way the Original did. The pre-conversion report lists the predictable ones under "Needs fixing" or "Improves the experience".

- **Folders moved up by conversion:** This site allows 3 levels of nested content. Conversion moves each folder nested too deep up to sit directly in its learning module, with the items directly in it: see "Folders moved up by conversion" below for where each one is now. Learners lose nothing, so this doesn't block release: fix it after the course opens.

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
| Content | SCORM items | 1 | 1 | Same |  |
| Content | Discussion links | 1 | 1 | Same |  |
| Content | LTI tool links | 0 | 0 | Same |  |
| Content | All items | 10 | 14 | Expected | Conversion adds folders. |
| Content | Content types carried over | 5 | 5 | Same | Added by conversion: Document +2; Folder +2. |
| Content | Folders moved up by conversion | 1 | 1 | Expected, should fix | This site allows 3 levels of nested content. Conversion moves each folder nested too deep up to sit directly in its learning module, with the items directly in it: see "Folders moved up by conversion" below for where each one is now. Learners lose nothing, so this doesn't block release: fix it after the course opens. |
| Content | Hidden items still hidden | 1 | 1 | Same |  |
| Grades | Grade columns | 5 | 4 | Expected | Ultra drops the weighted total column. |
| Groups | Groups in use | 1 | 0 | Needs action | Not carried over: Advanced Stream. Run the group repair, then re-scan. |
| Release conditions | Gated items still gated | 2 | 2 | Same |  |
| Release conditions | Conditions carried over exactly | 2 | 1 | Needs action | 1 lost only their group(s), on: Advanced Readings. The group repair should restore these. |
| Tests | Questions with partial-credit answer values | 1 | 0 | Needs action | 1 question(s) lost their answer values: run the partial-credit repair, then re-scan. |
| Tests | Questions drawn through random blocks and question sets | 5 | 5 | Same |  |
| Tests | Pools and question banks | 0 | 1 | Expected | Undeployed tests became question banks (a site setting, listed below). |
| Tests | Questions in tests | 6 | 6 | Same | 6 Multiple Choice question(s) are stored as Multiple Answer in Ultra (single answer). |
| Tests | Test exceptions | 0 | 0 | Same |  |
| Learner records | Attempts in progress | 1 | 1 | Same | Original: 1 tests. Ultra: 1 tests. |
| Learner records | Submissions waiting for grading | 0 | 0 | Same |  |
| Learner records | Grade and attempt records matching | 6 | 6 | Same |  |
| SCORM | SCORM records with the same resume state | 2 | 2 | Same | Bookmark, suspend data, status and score compared (2 from the engine's runtime record).  |
| Learner records | Unavailable students' records | 1 learner(s), 4 record(s) | 1 learner(s), 4 record(s) | Same | Compared as totals: grade records, attempts and SCORM records. |
| Grades | Hidden columns now visible | 1 | 1 | Needs action | Decide whether to hide, remove or keep: Placement Test |

## Folders moved up by conversion

These folders or learning modules were nested deeper in the Original than the site allows in Ultra. Conversion moved each one up to sit directly in its learning module, with the items directly in it; a folder that was inside another now sits beside it. Check that learners can still find them.

| Original location | Level in Ultra if not moved | Ultra location | Level now | Items in it: Original | Items in it: Ultra | Result |
|---|---|---|---|---|---|---|
| Course Content / Unit 1 / Further Reading | 3 | Course Content / Further Reading | 2 | 2 | 2 | Moved up, items kept |

## ID map

Every grade column in the Original, matched to the Ultra copy by its attached item. The full map for the batch is in `idmap.csv`, with the same columns. IDs are the numeric primary keys as stored in the database: `pk1` is `course_main.pk1` on the course row and `gradebook_main.pk1` on a grade column row; `course_contents_pk1` is `gradebook_main.course_contents_pk1`, the item the column belongs to.

| `table` | `orig_pk1` | `new_pk1` | `title` | `attached_item` | `orig_course_contents_pk1` | `new_course_contents_pk1` | `match_status` |
|---|---|---|---|---|---|---|---|
| course_main | 101 | 901 | Introduction to Portfolio Management |  |  |  | matched |
| gradebook_main | 1002 | 9002 | Module 1 Quiz | Module 1 Quiz | 10002 | 90002 | matched |
| gradebook_main | 1003 | 9003 | Placement Test | Placement Test | 10003 | 90003 | matched |
| gradebook_main | 1006 | 9006 | Module 1 Interactive | Module 1 Interactive | 10006 | 90006 | matched |
| gradebook_main | 1008 |  | Weighted Total |  |  |  | removed in Ultra (weighted total) |
| gradebook_main | 1009 | 9009 | Total |  |  |  | matched |

Grade columns by match: matched 4, removed in Ultra (weighted total) 1. An ambiguous or not-found column is resolved before hand-off; columns new in Ultra can be ignored.

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
