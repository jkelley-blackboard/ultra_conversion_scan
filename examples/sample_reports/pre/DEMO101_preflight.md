# Pre-conversion Report: DEMO101, Introduction to Portfolio Management

**Prepared for:** Sample University | **Scan:** 2026-11-30 08:00 (UTC-05:00) | **Batch:** sample_pre

> Generated from the LMS reporting database by convscan 0.4.0. Figures are as of the scan. Severity: 1 blocks learners, 2 needs fixing, 3 improves the experience, 0 to check by hand. Where each value comes from (`table.field`): [REPORT_KEY.md](REPORT_KEY.md).

## In short

**Not ready: 3 item(s) would block learners.**
- **Release conditions that depend on groups:** Restore the groups and their members after the conversion (scripted), then check access.
- **Test attempts open now:** Ask learners to submit before the freeze. Re-run this scan at the freeze.
- **Partial credit in tests that open the next step:** Restore the answer values in the Ultra copy before learners use it (scripted from the pre-conversion data).
- **Decisions needed:** 2 (listed at the end).
- **Findings by severity:** Blocks learners 3, Needs fixing 5, Improves the experience 1, To check 1.

## The course

| | |
|---|---|
| Course primary key (`course_main.pk1`) | 101 |
| External ID (`course_main.batch_uid`) | DEMO101 |
| New course ID | DEMO101-7777 |
| Available to learners now | No |
| Members | 4 (1 staff, 3 students) |
| Students in progress | 2 (2 active in the last 30 days, 0 not for 90 days or more, 0 never accessed) |
| Students completed or expired | 1 (unavailable: copied, and counted rather than read one by one) |
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
| **Hidden grade columns that learners will see** | Needs fixing | Yes | 1 grade column(s) are hidden from learners today but attached to items they can open: Placement Test. In Ultra a column shows whenever its item does, so learners will see these scores. They can't be hidden without hiding the item. | Agree whether learners seeing these scores is acceptable, and whether to tell them. Removing a column removes its grades. |
| **Folders nested deeper than Ultra allows** | Needs fixing | Yes | 1 folder(s) or learning module(s) are nested too deep for this site's 3 levels of nested content in Ultra (a learning module, a folder, then content), holding 2 item(s) directly: Course Content / Unit 1 / Further Reading (2 item(s)). Conversion moves each one up to sit directly in its learning module, with those items, and a folder nested inside another comes out beside it rather than inside it, so the course's structure changes. Every item stays reachable, so this doesn't block learners. With the additional nesting level (one more level; the site setting can't be undone), 0 of these would still move. | Ultra can't hold them at their old depth, so to restore the structure, remove a level above them (for example a content area that only groups others), then move them back; the hand-off report lists where each one landed. Or flatten them in the Original before the conversion. Or decide on the additional nesting level first. |
| **Partial credit in graded tests** | Needs fixing | Yes | 1 question(s) give partial credit for some wrong answers. Conversion sets those answers to 0%. Tests: Placement Test. | Restore the answer values in the Ultra copy (scripted from the pre-conversion data). |
| **Tests that draw questions from an undeployed test** | Needs fixing | No | 5 question(s) are drawn from 1 undeployed test(s) by: Module 1 Quiz. This site turns undeployed tests into question banks on conversion, and Blackboard's help says those banks lose random blocks, question sets and linked questions, so these tests may draw fewer questions in Ultra. | Check the hand-off report's count of drawn questions. If it drops, point the draws at the new question bank in the Ultra copy. |
| **Items that conversion puts in a folder of their own** | Improves the experience | Yes | 3 item(s). Conversion puts each one in a folder of its own name, so learners open the folder, then the item. Nothing is lost. | Unwrap them after the conversion by moving each item up and removing its folder. |
| **Items hidden from learners** | To check | No | 1 item(s) are hidden from learners: Instructor Notes. In conversion testing some hidden items came out visible. | Check each is still hidden in the Ultra copy before learners use it (the hand-off report lists any now visible). |

## Decisions needed

1. **Hidden grade columns that learners will see:** Agree whether learners seeing these scores is acceptable, and whether to tell them. Removing a column removes its grades.
2. **Folders nested deeper than Ultra allows:** Ultra can't hold them at their old depth, so to restore the structure, remove a level above them (for example a content area that only groups others), then move them back; the hand-off report lists where each one landed. Or flatten them in the Original before the conversion. Or decide on the additional nesting level first.

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
