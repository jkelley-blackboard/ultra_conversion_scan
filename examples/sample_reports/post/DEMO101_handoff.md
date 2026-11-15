# Conversion Hand-off Report: DEMO101, Introduction to Portfolio Management

**Prepared for:** Sample University | **Post-scan:** 2026-12-01 | **Baseline:** 2026-11-30 | **Batch:** sample_post

> Generated from the LMS reporting database by convscan 0.1.0, by comparing the Ultra copy with the Original as scanned before conversion.

## Summary

| | |
|---|---|
| Course | DEMO101 → **DEMO101-7777** (Ultra) |
| Learners | 4 members, 2 in progress |
| Checks | 21 same, 3 expected changes, 0 different, 4 need action, 0 not checked |
| Status | **4 item(s) need action before release** |

## Needs action before release

- **Groups in use:** Not carried over: Advanced Stream. Run the group repair, then re-scan.
- **Conditions carried over exactly:** 1 lost only their group(s), on: Advanced Readings. The group repair should restore these.
- **Questions with partial-credit answer values:** 1 question(s) lost their answer values: run the partial-credit repair, then re-scan.
- **Hidden columns now visible:** Decide whether to hide, remove or keep: Placement Test

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

## ID map

Every grade column in the Original, matched to the Ultra copy by its attached item. The full map for the batch is in `idmap.csv`.

| Kind | Original ID | Ultra ID | Title | Attached item | Match |
|---|---|---|---|---|---|
| course | _101_1 | _901_1 | Introduction to Portfolio Management |  | matched |
| grade column | _1002_1 | _9002_1 | Module 1 Quiz | Module 1 Quiz | matched |
| grade column | _1003_1 | _9003_1 | Placement Test | Placement Test | matched |
| grade column | _1006_1 | _9006_1 | Module 1 Interactive | Module 1 Interactive | matched |
| grade column | _1008_1 |  | Weighted Total |  | removed in Ultra (weighted total) |
| grade column | _1009_1 | _9009_1 | Total |  | matched |

Grade columns by match: matched 4, removed in Ultra (weighted total) 1. An ambiguous or not-found column is resolved before hand-off; columns new in Ultra can be ignored.

## Site conversion settings at the post-scan

| Setting | This site |
|---|---|
| Levels of nested content (3 by default, 4 with the additional level) | 3 |
| Content areas become learning modules | Yes |
| Folder and learning module descriptions become documents | No |
| Undeployed tests become question banks | Yes |

## Not checked by this scan

- What a learner sees on screen, and whether SCORM content resumes in the player.
- Whether files linked from the Content Collection still open.
- Systems outside the LMS that store course or grade column IDs: update them from the ID map.
- Each record of students who were unavailable or disabled at the pre-scan: their records are compared as totals, not one by one.
