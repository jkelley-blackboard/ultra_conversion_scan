# What the scan checks

This page is for anyone reading a pre-conversion report, or deciding what a report should flag. It
lists every rule in plain language: what the scan looks for, why it matters in an Ultra conversion,
and what the report recommends.

The rules themselves live in [src/convscan/rules/default.yaml](src/convscan/rules/default.yaml). That
file is the source of truth: when a rule changes there, update this page to match.

## How findings are reported

Each rule reads the results of one scan query and fires when it finds something. A finding in the
report gives the count, names a few example items (test titles, group names, column titles), says
why it matters and recommends an action.

Each rule has a tier. The report shows findings from most to least serious:

| Tier | Meaning |
|---|---|
| **1: Blocks learners** | Learners would be locked out, held back or lose work unless this is handled before or right after the conversion |
| **2: Needs fixing** | Something changes or goes missing in the conversion and needs repair or a decision, but learners can still pick up where they left off |
| **3: Improves the experience** | Optional tidy-up |
| **4: Ultra opportunity** | Using what Ultra offers beyond the Original. No rule uses this tier yet |
| **To check** | The scan can't tell from the data alone, or the behavior hasn't been tested yet. Someone needs to look |

Some rules are marked **needs a decision**: the report lists them for the institution to settle at
hand-off, because there's more than one reasonable answer.

**Confirmed** in the tables below means the conversion behavior was seen in testing or is documented
by Blackboard. **Not yet confirmed** means the rule flags a likely risk that still needs a test
conversion to prove.

## Tier 1: blocks learners

| What the scan looks for | Why it matters | What the report recommends | Confirmed |
|---|---|---|---|
| The new course ID already exists | The copy can't be made. This is often a leftover test copy | Remove or rename the existing course before the conversion (needs a decision) | Yes |
| The new course ID is longer than the site's limit | The copy fails | Agree a shorter ID for the course (needs a decision) | Yes |
| Test attempts open now | An attempt still open at the freeze arrives in Ultra in progress | Ask learners to submit before the freeze, then re-run the scan at the freeze | Yes |
| Timed tests with attempts open now | A timed attempt left open over the freeze may run out or submit itself | Clear these attempts before the freeze, or confirm how they arrive in Ultra | Not yet |
| Assignments saved as drafts but not submitted | The drafts may not arrive in Ultra | Ask learners to submit before the freeze, or check the drafts arrive | Not yet |
| Partial-credit questions in tests whose score opens the next step | Conversion sets partial credit on wrong answers to 0%, so learners who haven't taken the test yet could score lower and be held back | Restore the answer values in the Ultra copy before learners use it (scripted from the pre-conversion data) | Yes |
| Partial-credit questions in tests whose score sends learners down different paths | The same 0% change could send learners down the wrong path | Restore the answer values, then check one learner on each path | Yes |
| Release conditions that depend on groups | Groups aren't carried over, so the content closes to the learners it was meant for | Restore the groups and their members after the conversion (scripted), then check access | Yes |

## Tier 2: needs fixing

| What the scan looks for | Why it matters | What the report recommends | Confirmed |
|---|---|---|---|
| Partial-credit questions in any graded test | Conversion sets partial credit on wrong answers to 0%, which lowers some scores | Restore the answer values in the Ultra copy (scripted) | Yes |
| Groups with members | Groups aren't carried over | Restore the groups and their members after the conversion (scripted) | Yes |
| Course links | Conversion drops them, apart from the course links it creates for discussions | Recreate each link in the Ultra copy, or replace it with a link to the item | Yes |
| Tool links (links to course tools such as Announcements or the Gradebook) | Conversion drops them | Recreate the ones learners need; most course tools are already in Ultra's course navigation | Yes |
| Hidden grade columns attached to items learners can open | In Ultra a column shows whenever its item does, so learners will see these scores. They can't be hidden without hiding the item | Agree whether learners seeing these scores is acceptable, and whether to tell them. Removing a column removes its grades (needs a decision) | Yes |
| Hidden grade columns not attached to an item (totals, calculated or manual columns) | These can be hidden on their own in Ultra, but conversion may not keep them hidden | Check each is still hidden in the Ultra copy, and hide it there if not | Not yet |
| Release conditions on discussions | They aren't carried over, so the discussions open to everyone in the course | Re-create the conditions in the Ultra copy, or agree to leave the discussions open | Yes |
| Folders or learning modules nested deeper than the site allows in Ultra (3 levels by default: a learning module, a folder, then content) | Conversion moves each one up to sit directly in its learning module, with its items, and a folder nested in another comes out beside it. The structure changes, but every item stays reachable | Ultra can't hold them at their old depth, so to restore the structure, remove a level above them (for example a content area that only groups others), then move them back (the hand-off report lists where each landed). Or flatten them in the Original first. While the site's nesting setting is undecided, the report also says how many would still move with the additional nesting level (needs a decision) | Yes |
| Tests that draw questions from an undeployed test | The site turns undeployed tests into question banks, which may lose random blocks, question sets and linked questions, so the test may draw fewer questions | Check the drawn-question count in the hand-off report. If it drops, point the draws at the new question bank | Not yet |
| Folder descriptions with links, images, embedded media, attached files or more than 750 characters, on a site that keeps descriptions as plain text | Conversion keeps a description as plain text of up to 750 characters, so the rest is lost | Recreate what learners need as items in the folder, or turn on the setting that converts descriptions to documents first (needs a decision) | Not yet |
| Undeployed tests, on a site that doesn't turn them into question banks | Conversion puts them in a hidden folder at the top of the Ultra course, each with a grade column. Learners can't see them, but the extra columns appear in the ID map | Keep the folder hidden or remove it after the conversion. Removing it removes the extra columns too | Yes |
| Content types Ultra doesn't support: wikis, blogs, achievements, module pages, syllabus, self and peer assessment | Conversion removes them | Rebuild them in Ultra (for example as a document, discussion or LTI tool), or agree to drop them (needs a decision) | Yes |
| Question types Ultra doesn't support: File Upload, Opinion Scale, Ordering, Quiz Bowl | Conversion removes them, so the test's points change | Replace these questions before or after converting. If the test opens the next step, treat it as blocking | Yes |
| Tests that require a secure browser | The setting may not carry over | Check the setting in the Ultra copy before learners use it | Not yet |
| Tests that use a proctoring service | The setting may not carry over | Check the setting in the Ultra copy before learners use it | Not yet |

## Tier 3: improves the experience

| What the scan looks for | Why it matters | What the report recommends | Confirmed |
|---|---|---|---|
| Grade columns not attached to any item | They were entered by hand or left over, and add clutter | Optional tidy-up after the conversion | Not yet |
| Items with display dates | The dates may no longer make sense in the new course | Check the dates in Ultra | Not yet |
| Items (documents) | Conversion puts each one in a folder of its own name (seen in every course checked), so learners open the folder, then the item. Nothing is lost | Unwrap them after the conversion by moving each item up and removing its folder | Yes |
| Folder descriptions with formatting, on a site that keeps descriptions as plain text | The formatting (bold, italics, lists, tables, headings, styles) is lost; the words are kept | Check the descriptions still read well as plain text | Not yet |
| Folder descriptions, on a site that turns them into documents | Each description becomes a document inside its folder, so each folder gains an item | Remove the documents learners don't need, or turn off the setting first | Not yet |

## To check

| What the scan looks for | Why it matters | What the report recommends | Confirmed |
|---|---|---|---|
| Items hidden from learners | In conversion testing some hidden items came out visible, for reasons not yet known | Check each is still hidden in the Ultra copy before learners use it (the hand-off report lists any now visible) | Not yet |
| The course is available to learners | Bulk copy and convert will still copy it (Blackboard's help says otherwise, but available courses copied in conversion testing), and work learners do in the Original after the copy isn't carried over | Make the course unavailable (closed) before the copy that carries learners over. It's a required step that the copy doesn't check | Yes |
| SCORM attempts in progress | In testing these resumed in Ultra. The hand-off report compares each learner's saved place | Check the SCORM row in the hand-off report, and open a sample in the learner view if it shows differences | Yes |
| Submissions waiting to be graded | They carry over and can be graded in Ultra | Agree who grades them, and whether before the freeze or in Ultra (needs a decision) | Yes |
| Ungraded work from students who can no longer open the course | They carry over and can be graded in Ultra | Agree who grades them, and whether before the freeze or in Ultra (needs a decision) | Yes |
| Content types not yet covered by conversion testing | Nobody has seen how they arrive in Ultra | Convert one example in a test course and check it before this course converts | Not yet |
| Test exceptions (extra time or attempts) for individual learners or groups | Not yet known whether they carry over | Check them in the Ultra copy | Not yet |
| Test exceptions given to a group | Groups aren't carried over | Check the exceptions after the groups are restored | Not yet |
| Questions that give credit in proportion to how much is right (matching, jumbled sentence and similar) | Not yet known whether the setting carries over | Check the partial-credit setting on one of them | Not yet |
| Release conditions on calculated columns | A test that feeds the column controls access indirectly | Check whether any test feeding the column uses partial credit, and check the column's value for a sample of learners | Not yet |
| Release conditions that name individual learners | Not yet known whether they carry over | Check them in the Ultra copy | Not yet |
| Links that open HTML pages in the Content Collection | The pages may have Original course addresses built in | Open the pages and look for links to the Original course | Not yet |
| Links to files in the Content Collection | The files have to stay where they are | Keep the files in place, and open a sample in the Ultra copy | Not yet |
| LTI tool links | Each tool has to launch from the new course | Launch each tool once in the Ultra copy | Not yet |
| SCORM packages with a time limit | Not yet known whether the limit carries over | Check the limit in the Ultra copy | Not yet |

## What the scan doesn't check

Every report lists these under "Not checked", because the database can't answer them:

- What a learner sees on screen. Check with a learner view.
- Links inside SCORM packages and Content Collection pages that point to the Original course.
- Whether files linked from the Content Collection still exist.
- Systems outside the LMS that store course or grade column IDs. Give them the ID map from the
  hand-off report.

## How the hand-off report relates to these rules

The hand-off report compares each converted copy with its Original. It doesn't use these rules: its
checks are in [src/convscan/compare.py](src/convscan/compare.py). Each check has a result, and two of
the results line up with the tiers above:

| Hand-off result | Meaning | Tier it lines up with |
|---|---|---|
| Needs action | A known loss that the scripted repairs fix (groups, answer values), or something to settle before release | Tier 1, and tier 2 items with a scripted repair |
| Expected, should fix | Conversion always does this and learners lose nothing, so it doesn't hold up release, but it should be put right after the course opens | Tier 2, or tier 3 for wrapped items |

These are the checks that give **Expected, should fix**:

| Check | What it finds | Pre-conversion rule |
|---|---|---|
| Folders moved up by conversion | Every folder nested too deep was found in the copy, with its items | Folders nested deeper than Ultra allows |
| Undeployed tests in a hidden folder | The hidden folder conversion adds for undeployed tests | Undeployed tests, on a site that doesn't turn them into question banks |
| Grade columns | More columns in the copy, some of them belonging to those undeployed tests | The same rule |
| Items wrapped in a folder by conversion | Items now inside a folder of their own name (for example `Note` inside folder `Note`): every Original item, plus description documents left alone in a folder whose other contents moved up | Items (documents), and folder descriptions on a site that turns them into documents (both tier 3) |

Grade columns hidden in the Original get two hand-off checks. "Hidden columns now visible" (marked visible in the copy) gives **Needs action**. "Hidden columns that learners see with their item" gives **Expected**: the copy still marks the column hidden, but it's attached to an item learners can open, and Ultra shows it with the item. The pre-conversion rule "Hidden grade columns that learners will see" lists those in advance.

The hand-off report's "Hidden items now visible to learners" gives **Needs action**: hide them before release. The pre-conversion rule "Items hidden from learners" lists them in advance.

Restructuring that isn't a conversion change, such as removing a content area the Original already
had, is outside both reports.
