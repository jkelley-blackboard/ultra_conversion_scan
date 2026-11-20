# Pre-conversion Report: DEMO102, Ethics in Practice

**Prepared for:** Sample University | **Scan:** 2026-11-30 08:00 (UTC-05:00) | **Batch:** sample_pre

> Generated from the LMS reporting database by convscan 0.4.1. Figures are as of the scan. Severity: 1 blocks learners, 2 needs fixing, 3 improves the experience, 0 to check by hand. Where each value comes from (`table.field`): [REPORT_KEY.md](REPORT_KEY.md).

## In short

**No blocking items found by the scan.**
- **Decisions needed:** 1 (listed at the end).
- **Findings by severity:** Blocks learners 0, Needs fixing 0, Improves the experience 1, To check 1.

## The course

| | |
|---|---|
| Course primary key (`course_main.pk1`) | 102 |
| External ID (`course_main.batch_uid`) | DEMO102 |
| New course ID | DEMO102-7777 |
| Available to learners now | No |
| Members | 4 (1 staff, 3 students) |
| Students in progress | 2 (2 active in the last 30 days, 0 not for 90 days or more, 0 never accessed) |
| Students completed or expired | 1 (unavailable: copied, and counted rather than read one by one) |
| Disabled students | 0 (copied too) |
| Content | 6 items: 1 tests, 1 assignments, 0 SCORM, 0 discussion links, 0 LTI links |
| Gated items | 0 |
| Grade columns | 2 |
| Groups | 0 |
| Partial-credit questions | 0 |
| Discussion posts | 0 |

## What to watch

| Risk | Severity | Known? | What the scan found | Action |
|---|---|---|---|---|
| **Items that conversion puts in a folder of their own** | Improves the experience | Yes | 2 item(s). Conversion puts each one in a folder of its own name, so learners open the folder, then the item. Nothing is lost. | Unwrap them after the conversion by moving each item up and removing its folder. |
| **Work waiting to be graded** | To check | Yes | 1 submission(s) are waiting for a grader: none listed. They carry over and can be graded in Ultra. | Agree who grades them, and whether before the freeze or in Ultra. |

## Decisions needed

1. **Work waiting to be graded:** Agree who grades them, and whether before the freeze or in Ultra.

## Site conversion settings

These site-wide settings decide how the course converts. Agree them before the first batch: the additional nesting level can't be undone.

| Setting | This site |
|---|---|
| Blackboard LMS version | 4001.7.0-rel.4+a1cda0a |
| Content takes the release conditions of its folder or learning module | Yes |
| Levels of nested content (3 by default, 4 with the additional level) | 3 |
| Content areas become learning modules | Yes |
| Folder and learning module descriptions become documents | No |
| Undeployed tests become question banks | Yes |

## Not checked by this scan

- What a learner sees on screen (check with a learner view).
- Links inside SCORM packages and Content Collection pages that point to the Original course.
- Whether files linked from the Content Collection still exist.
- Systems outside the LMS that store course or grade column IDs (give them the ID map from the hand-off report).
- Each record of students who are unavailable or disabled: the scan counts their grades, attempts and SCORM records instead of reading them one by one.
- Folder descriptions that lose links, media or files (S3e was not run).
- Folder descriptions that lose their formatting (S3e was not run).
- Folder descriptions that become documents (S3e was not run).
- SCORM packages with a time limit (S6 was not run).
