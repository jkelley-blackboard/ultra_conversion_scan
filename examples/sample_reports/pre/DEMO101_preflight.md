# Pre-conversion Report: DEMO101, Introduction to Portfolio Management

**Prepared for:** Sample University | **Scan:** 2026-11-30 | **Batch:** sample_pre

> Generated from the LMS reporting database by convscan 0.1.0. Figures are as of the scan. Severity: 1 blocks learners, 2 needs fixing, 3 improves the experience, 0 to check by hand.

## In short

**Not ready: 3 item(s) would block learners.**
- **Release conditions that depend on groups:** Restore the groups and their members after the conversion (scripted), then check access.
- **Test attempts open now:** Ask learners to submit before the freeze. Re-run this scan at the freeze.
- **Partial credit in tests that open the next step:** Restore the answer values in the Ultra copy before learners use it (scripted from the pre-conversion data).
- **Decisions needed:** 1 (listed at the end).
- **Findings by severity:** Blocks learners 3, Needs fixing 3, Improves the experience 0, To check 0.

## The course

| | |
|---|---|
| New course ID | DEMO101-7777 |
| Available to learners now | No |
| Members | 4 (1 staff, 3 students) |
| Students in progress | 2 (2 active in the last 30 days, 0 not for 90 days or more, 0 never accessed) |
| Students completed | 1 |
| Disabled students | 0 (copied too) |
| Content | 10 items: 2 tests, 0 assignments, 1 SCORM, 1 discussion links, 0 LTI links |
| Gated items | 2 |
| Grade columns | 5 |
| Groups | 1 |
| Partial-credit questions | 1 |
| Discussion posts | 6 |

## What could go wrong

| Risk | Severity | Known? | What the scan found | Action |
|---|---|---|---|---|
| **Release conditions that depend on groups** | Blocks learners | Yes | 1 group(s) control access to content: Advanced Stream. Groups are not carried over, so this content would be closed to the learners it was meant for. | Restore the groups and their members after the conversion (scripted), then check access. |
| **Test attempts open now** | Blocks learners | Yes | 1 attempt(s) are open in 1 test(s): Module 1 Quiz. An attempt still open at the freeze arrives in Ultra in progress. | Ask learners to submit before the freeze. Re-run this scan at the freeze. |
| **Partial credit in tests that open the next step** | Blocks learners | Yes | 1 question(s) with partial credit are in tests whose score opens the next step. Conversion sets partial credit on wrong answers to 0%, so learners who haven't taken the test yet could score lower and be held back. | Restore the answer values in the Ultra copy before learners use it (scripted from the pre-conversion data). |
| **Groups with members** | Needs fixing | Yes | 1 group(s) with members: Advanced Stream. Groups are not carried over. | Restore the groups and their members after the conversion (scripted). |
| **Grade columns hidden from learners** | Needs fixing | Yes | 1 grade column(s) are hidden from learners today: Placement Test. Ultra can't hide a column separately from its item, so some may become visible. | Decide at hand-off whether each should be hidden, removed or left visible. |
| **Partial credit in graded tests** | Needs fixing | Yes | 1 question(s) give partial credit for some wrong answers. Conversion sets those answers to 0%. Tests: Placement Test. | Restore the answer values in the Ultra copy (scripted from the pre-conversion data). |

## Decisions needed

1. **Grade columns hidden from learners:** Decide at hand-off whether each should be hidden, removed or left visible.

## Site conversion settings

These site-wide settings decide how the course converts. Agree them before the first batch: the additional nesting level can't be undone.

| Setting | This site |
|---|---|
| Levels of nested content (3 by default, 4 with the additional level) | 3 |
| Content areas become learning modules | Yes |
| Folder and learning module descriptions become documents | No |
| Undeployed tests become question banks | No |

## Not checked by this scan

- What a learner sees on screen (check with a learner view).
- Links inside SCORM packages and Content Collection pages that point to the Original course.
- Whether files linked from the Content Collection still exist.
- Systems outside the LMS that store course or grade column IDs (give them the ID map from the hand-off report).
- SCORM packages with a time limit (S6 was not run).
