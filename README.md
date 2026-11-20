# ultra_conversion_scan (`convscan`)

`convscan` is a Python command-line tool for checking Blackboard LMS courses before and after they're
converted from the Original course view to the Ultra course view. It's designed to read the Blackboard
LMS database through the Direct Data Access (DDA) service, and it writes plain-language reports about
what it finds.

It connects to the site's DDA database (a read-only PostgreSQL replica of production) with a read-only
session, runs a fixed set of `SELECT` queries, saves the results, applies a table of rules, and writes
Markdown reports. There's no AI and no analyst in the loop: the same data always gives the same report.

**You need:** Python 3.10 or later, and DDA credentials for the site (a read-only DDA user).

**About DDA:** the [DDA Resource Guide](https://jkelley-blackboard.github.io/DDA/) covers the service and
its schema, and the [DDA repository](https://github.com/jkelley-blackboard/DDA) has a SQL library, a
machine-readable schema (`schema.json`) and tools. Check a table or column there before adding it to a
query.

**Before each LMS release,** check the schema changes against the tables and columns the queries use (the
S0 list in the SQL file). Blackboard publishes the database documentation for every build, released or
not, to [bbprepo](https://bbprepo.blackboard.com/#browse/browse:releases:bbdn%2Fschema). The DDA
repository tracks Test/Stage releases and records each delta on its
[Schema Changes](https://jkelley-blackboard.github.io/DDA/schema-changes.html) page (`tools/diff_schema.py`).
If the next release isn't published yet, diff against the latest build on bbprepo for an interim list.
After the release, run `convscan check` on the site.

**Status (2026-11-15):** working, and tested on four real copy-and-convert runs on a demo site (2 to
10 learners per course). Version 0.2.0 reads learner records one by one only for students in progress,
and adds rules for over-deep folders and draws from undeployed tests; both changes were checked
read-only on the demo site. Not yet run on a production site.

**See it first:** [examples/sample_reports/](examples/sample_reports/) has a pre-conversion report,
a hand-off report and an ID map for two invented courses, one with typical losses and one clean.

**Maintainer:** Jeff Kelley, Blackboard (built November 2026). A public repository, shared with
institutions converting courses and with Blackboard teams. No client data is stored here: runs and
reports stay on the machine that runs them.

## Using it

**[USER_GUIDE.md](USER_GUIDE.md)** is for the people who run batches and read the reports: install
and connect, choosing courses, the five steps of a batch, reading each report, looking after the data,
and what to do when something goes wrong. This README is for maintaining the tool.

The five steps, in short, after `convscan init` writes a config: `convscan check` once per site; `convscan pre` before the batch (its data is
the baseline); `convscan tasks --wait` during the copy; `convscan post` against the baseline after it;
`convscan post` again after repairs.

## Development setup

Python 3.10 or later. From the repo folder:

```
pip install -e ".[dev]"      # pip3 on macOS and Linux
python -m pytest             # python3 on macOS and Linux
```

This installs `psycopg2-binary`, `PyYAML`, `Jinja2` and pytest. None of the tests need a database. The
connection comes from the config's `db:` block, overridden by any `DDA_HOST`, `DDA_PORT`, `DDA_DBNAME`
or `DDA_USER` variable; the password from `DDA_PASSWORD` or a hidden prompt, never from a file
(`config.load` rejects one). See USER_GUIDE.md, "Connect".

Severity in the rule table is a number: 1 blocks learners, 2 needs fixing, 3 improves the experience,
4 makes the most of Ultra, 0 to check by hand. Hand-off results are `same`, `expected`, `different`,
`action` (shown as "Needs action") and `not checked`. [RULES.md](RULES.md) lists every rule in plain
language: what it looks for, why it matters and what the report recommends.

## How it works

```
courses (manifest or node)
  -> the queries, filled in for those courses     src/convscan/sql/conversion_scan.template.sql
  -> run against the database, read-only          -> runs/<name>/data/*.csv
  -> the rule table                               src/convscan/rules/default.yaml  -> findings
  -> the compare (post-scan only)                 baseline against copies           -> checks, idmap.csv
  -> the report templates                         src/convscan/templates/           -> runs/<name>/reports/
```

Three design choices:

- **Judgment lives in the rule table, not the code.** To change what a report flags, or how it says it,
  edit the YAML (see "Writing rules").
- **The database connection is swappable.** `runner.py` needs only one method, `query(sql)`, returning
  columns and rows. A Reporting Framework runner could replace the direct connection without touching
  the rules, compare or templates.
- **The post-scan re-reads the Originals.** Learners may keep working after the pre-scan, so a copy that
  matches either the baseline or the Original as it is now counts as a match.

## The queries

Each query has a label, used in rules, run folders and these notes. Those marked "per learner" return
a row per learner and are the large ones. S7, S8b and S10 read only students in progress by default
(see "Which learners are read one by one" below).

| Label | What it reads |
|---|---|
| S0 | Every table and column the queries use (`convscan check`) |
| S1 | Course identity (course ID, primary key, external ID `batch_uid`), availability, and whether the new ID is free |
| S2 | Members: staff, students in progress, completed and disabled, recent access |
| S2b | Totals for unavailable and disabled students: learners, grade records, attempts, SCORM records |
| S3 | Content counts: tests, assignments, SCORM, discussions, LTI, hidden and dated items, Content Collection links |
| S3c | Every content type in the course, with how many items of each are hidden |
| S3b | Every item with its folder path, availability and depth |
| S3d | Folders and learning modules deeper than the site's nesting limit in Ultra (Original courses only) |
| S3e | Folder and learning module descriptions (Original courses only): text length, formatting, links, media, attached files, and what the site's descriptions setting does with them |
| S4 | Grade columns: type, attached item and whether learners can open it, visibility, calculated or not |
| S5b | Questions with partial credit per course, by how their tests are used (route learners, open the next step, or just graded) |
| S5c | Each partial-credit question's answer values: the repair list and its baseline |
| S5d | Question types in every test, including those Ultra removes |
| S5e | Pools, question banks, and questions drawn into tests by random blocks |
| S5f | Undeployed tests, how many questions other tests draw from each, and whether the site turns them into question banks |
| S6 | SCORM package settings |
| S7 | Per learner in progress: grades and attempts on every column (open, submitted, waiting for grading) |
| S8, S8b | Groups and what uses them; per learner: group membership |
| S9 | Every release condition, with its groups and named learners |
| S10 | Per learner in progress: SCORM attempts and a fingerprint of the saved resume state |
| S11 | Discussion volume |
| S12 | Test settings (time limit, auto-submit, attempts, passwords, proctoring) and open attempts |
| S12b | Per learner or group: test exceptions (extra time or attempts) |
| S13 | System tasks for each course (copy and convert, restore, follow-on tasks) |
| S14 | The site's conversion settings, its LMS version and the release-condition inheritance flag |
| M2 | The column map, Original to copy (post-scan only) |

The header of the SQL file lists the code values these queries rely on, confirmed on a demo site.

## What conversion changes, and how the compare allows for it

Learned from real conversions on demo (2026-11-14) and Blackboard's help. The compare treats these as
expected, not as differences:

- **Titles** lose HTML (`<u>Chapter 1</u>` becomes `Chapter 1`), and dashes and curly quotes become plain
  text. Titles are compared without either.
- **Discussion links** take the forum's own name and gain a course link beside them, so they're counted
  rather than matched by title.
- **A blank page** becomes a folder plus a document. **An assignment** becomes an Ultra assessment.
  **Multiple Choice** questions are stored as Multiple Answer. **Tests with instructions** gain a
  "Presentation Only" text block.
- **Conversion adds folders**, and repeats some release conditions on them.
- **Calculated columns** all become one calculated type in Ultra; the **Weighted Total** is dropped.
- **Grade columns with the same title** (four "Total" columns, say) are paired by their visibility, then
  by creation order, since the copy keeps the order.
- **Empty, unused groups** disappear without consequence. Groups in use are a loss to repair.
- **Undeployed tests** become hidden tests or question banks, depending on a site setting (S14).
- **SCORM resume state** may sit only in the engine's runtime record (`scormregistration.runtime_data`,
  a length plus zlib-compressed XML), not in its tables. `scorm.py` decodes it while reading and keeps
  only a fingerprint and the bookmarks, never the learner's raw state.

Known losses, which the reports flag for action: groups, release conditions on discussions,
partial-credit answer values, grade columns that were hidden becoming visible, and content and
question types Ultra doesn't support (wikis, blogs, achievements, module pages, syllabus, self and
peer assessments; File Upload, Opinion Scale, Ordering and Quiz Bowl questions).

## Writing rules

Rules live in [src/convscan/rules/default.yaml](src/convscan/rules/default.yaml). One rule:

```yaml
- id: open_attempts_at_freeze
  title: Test attempts open now
  source: S12                      # the query it reads
  where: {open_attempts__gt: 0}    # which rows count (optional; conditions combine with AND)
  measure: sum(open_attempts)      # count | sum(col) | max(col) | min(col) | any(col) | distinct(col)
  threshold: 0                     # the rule fires when the measure is above this
  severity: 1
  known: true                      # a known conversion behavior with a known fix
  examples: test_title             # a column to list in the finding (first five values)
  says: "{value} attempt(s) are open in {n} test(s): {examples}."
  action: Ask learners to submit before the freeze. Re-run this scan at the freeze.
  decision: false                  # true lists it under "Decisions needed"
```

**Conditions in `where`:** `col: value` (equals; a list means any of), or a suffix on the column name:
`__ne` (not equal; a list means none of), `__gt`, `__gte`, `__lt`, `__notnull: true`, `__null: true`
(an empty value counts as null), `__contains`, `__startswith`. Values compare as numbers or true/false
where they look like them.

**Wording:** `says` and `action` can use `{value}` (the measure), `{n}` (rows that matched),
`{examples}`, `{first[col]}` (a column from the first matching row) and `{sums[col]}` (a column's
total over the matching rows). They appear in reports for the institution, so keep them plain, and
don't use em-dashes.

**Thresholds from config:** `threshold: {config: max_course_id_length}` takes the value from the config
file; 0 there switches the rule off.

**Text that a config setting switches:** an `extra` block (`config`, and any of `says`, `action`,
`decision`) adds its text to the finding, and its decision flag, only while that config setting is
true (true when the setting isn't in the config). The nesting rule's what-if uses `nesting_what_if`.

A rule whose query wasn't run (for example with `--no-learner`) appears under "Not checked" in the
report instead of passing silently.

## Data handling

convscan saves no names, usernames, email addresses or student IDs. Learners appear in the saved
data only as internal database keys (`users_pk1`, a sequential number), and the reports contain
counts only.

| What | Saved where | About learners |
|---|---|---|
| Reports, batch summary | `reports/` | Counts only. Titles of courses, items, columns and groups appear; group names are whatever the course author typed |
| `idmap.csv` | `reports/` | Nothing: course and grade column IDs as numeric `pk1` values with their table, the items' `course_contents_pk1` and the courses' `batch_uid`, all under their database names |
| `REPORT_KEY.md` | `reports/` | Nothing: where each value in that batch's reports comes from, as `table.field`, with the sections for the run type (pre or post). Share it with the reports. Template: [report_key.md.j2](src/convscan/templates/report_key.md.j2) |
| `run.json` | Run folder | Nothing: courses, settings, row counts, timings, replica lag |
| S7, S8b, S10, S12b, and S9's named users | `data/*.csv` | One row per learner by internal key: grades, attempts, group, test exceptions, SCORM location. S7, S8b and S10 cover students in progress only, unless `--all-learners` |
| S2b | `data/*.csv` | Totals per course for unavailable and disabled students: no one's records |
| SCORM runtime state | Not saved | Decoded while reading and replaced by a fingerprint |
| `diff_learner_records.csv` | `data/` | Internal key, column and the two values, for each mismatch |

No query selects a name, username or email (the SQL header says so, and `convscan sql` prints exactly
what runs). `--no-learner` leaves out the per-learner queries altogether.

**Which learners are read one by one** (since 2026-11-15). The `{LEARNERS}` placeholder in S7, S8b and
S10 is filled in by `kit.py`:

- **`pre` (default):** `and cu.available_ind = 'Y'`, students in progress only. Unavailable and disabled
  students can't resume, so S2b totals their records instead, and `check_inactive_records` compares the
  totals. `run.json` records `"learners": "active"`.
- **`pre --all-learners`:** empty, every enabled student, as before. Recorded as `"all"`.
- **`post`:** the learners its baseline read, course by course, on both the copy and the `_now`
  re-read (`kit.learner_filter`). Matching on the baseline's learners, not their state now, means a
  learner whose access ends or is extended between the scans is still compared. Per course, so a
  learner in progress in one course isn't read in another where they're inactive. A baseline without
  `learners` in its `run.json` predates the change and read everyone, so its post-scan does too.

The post filter is a `VALUES` list of (course, learner) pairs, two per learner (Original and copy).
At a large site's scale (200,000 learners in progress, say) a 100-course batch could make that list a few
megabytes per query. That's fine for PostgreSQL, but if it's slow, load the pairs into a temporary table instead.

A run has two folders (`paths.py`): its data folder, `data_dir/<name>`, holds `run.json` and
`data/*.csv` (one per query; post-scans add `S2_now`, `S2b_now`, `S7_now` and `S10_now`, the Originals re-read);
its reports folder, `reports_dir/<name>`, holds the reports, `idmap.csv` and a copy of `run.json`.
`run.json` records the reports folder, so `render` writes back to it. A path given as `--out` keeps
the older single-folder layout. Git ignores `runs/`. What the scan can't check is
listed in USER_GUIDE.md and in each report's "Not checked" section.

## Planned work

**Before production:**

- Run `check` and `pre` on a production site, starting with its largest course, and time them.
- Confirm `check` can read the replica lag there. The DDA user may not be allowed to call
  `pg_last_wal_receive_lsn()` and the related functions; if not, `post` runs with the lag shown as
  unknown and the hand-off report says so.
- Agree the new course ID format with the institution (the hyphen above), and read the site's
  conversion settings with them (S14) before the first batch.

**Gaps found in the demo test:**

- Submitted files, feedback and rubrics aren't compared.
- Test settings are scanned but not compared; assignment settings aren't scanned.
- Group membership after a repair (S8b) and discussion post counts (S11) aren't compared.
- After the partial-credit repair, compare each question's answer values with the baseline, not just
  the count. The repair has to handle Multiple Choice stored as Multiple Answer.
- Calculated column values could be compared through the REST gradebook API.
- The nesting rule (S3d, added 2026-11-15) counts an Original content area as level 1 in Ultra, read
  from how demo stores Ultra courses. Confirm it on a conversion: `FL3906_orig` on demo has two folders
  at level 4.
- The undeployed-test rule (S5f, added 2026-11-15) relies on Blackboard's help for what the question
  bank loses. A test conversion of a course where a test draws from an undeployed test (on demo:
  `CBU_BUS_535`) would show whether the draws survive.
- Not scanned yet: text grade schemas (Ultra converts them to points) and course menu items (Ultra
  has no course menu).
- Rules that haven't yet fired on real data: test exceptions, open assignment drafts, timed attempts
  open at conversion, learner activity after the pre-scan.

**Scale** (held until production runs are closer). Most courses are small, but a course with
thousands of learners and dozens of graded items (one test course had 8,500 learners and 37 items,
about 315,000 learner rows) is read three times by a post-scan and held in memory. Reading only
students in progress (2026-11-15) already cuts this wherever most learners have completed or expired.
Next, in order of payoff:

1. Compare one fingerprint per course and column (and per SCORM package), computed in the database;
   fetch learner rows only where fingerprints differ.
2. Re-read the Originals only for columns that differ.
3. Scan the largest courses on their own, one at a time. (Time of day doesn't matter: DDA is a read
   replica, so scans don't load the production database.)
4. Stream results instead of loading them whole, and compress the CSVs.

Done 2026-11-15: S7 and S10 apply the learner filter before counting attempts or reading SCORM
records (S10 no longer reads other learners' `runtime_data`); S8 and S9 count with joins, not a
lookup per row; S13 matches copy tasks with hashable joins. Every query returned identical results
before and after on 13 demo courses, in all three learner modes.

**Other:**

- A Reporting Framework runner (does it accept the recursive S3b, `md5` and `string_agg`, and results
  this large?).
- Item matching by folder path (M1). Today items match by normalized title and type, and conditions by
  their content.
- Word output with the Blackboard brand template.

## Code layout

```
src/convscan/
  cli.py          the commands
  config.py       defaults, the YAML config, finding it, and the starter config for init
  paths.py        where a run's data and reports go; the synced-folder warning
  scope.py        which courses: manifest or hierarchy node
  kit.py          loads the SQL file, fills in the courses, splits it into labeled queries
  runner.py       the database connection, running the queries, saving and loading runs
  scorm.py        decodes SCORM runtime records into fingerprints
  rules.py        applies the rule table
  compare.py      the post-scan compare and the ID map
  report.py       course facts and rendering the reports
  sql/            conversion_scan.template.sql: every query
  rules/          default.yaml: the rule table
  templates/      preflight.md.j2, handoff.md.j2, batch_summary.md.j2, report_key.md.j2
tests/
  test_core.py        the pieces: splitting the SQL, choosing courses, rules, SCORM decoding
  test_end_to_end.py  renders pre and post reports from invented runs and checks what they say
  test_connection.py  connection settings, and the password never in a file
  test_paths.py       data and reports folders, the synced-folder warning, finding the config, init
  test_replica.py     reading the replica lag
  sample_data.py      those invented runs (two courses, no real data)
examples/
  manifest.csv        a manifest to copy
  sample_reports/     the reports test_end_to_end checks, rendered for reading
  build_examples.py   rebuilds sample_reports/
```

Run `python -m pytest` after any change. None of the tests need a database.

## Common changes

| To | Do this |
|---|---|
| Mark a content type as tested (after a test conversion shows it works) | Add it to the `cnthndlr_handle__ne` list in the `content_type_untested` rule, and give it a plain name under `labels` in the same file |
| Add or reword a finding | Edit [rules/default.yaml](src/convscan/rules/default.yaml) (see "Writing rules"), then `convscan render` a saved run to see the result |
| Teach the compare a new expected conversion behavior | Find the area's `check_*` function in [compare.py](src/convscan/compare.py) (the `CHECKS` list at the bottom gives the order). Title and type rules are near the top (`norm`, `_HANDLER`, `_RENAMED_BY_CONVERSION`); the column map's matching is in the M2 query |
| Add a check to the hand-off | Write a `check_*` function that takes a `Pair` and calls `pair.add(...)`, and add it to `CHECKS` |
| Add a query | Add it to the SQL file with a header line `-- S<n>. What it reads`, add its tables and columns to S0, add the label to `EXPECTED` in `tests/test_core.py`, and to the query table in this README. If it returns a row per learner, add it to `LEARNER` in `kit.py`, and put `{LEARNERS}` on its `course_users cu` join so it reads the same learners as S7 |
| Change what a report looks like | Edit the template in [templates/](src/convscan/templates/), then `convscan render` a saved run |
| Refresh the examples | `python examples/build_examples.py`, and commit the result |

**Editing the SQL:** queries are separated by a semicolon at the end of a line, so a comment line must
never end in one (a test checks this). Never write a placeholder with its braces in a comment.

Terms (Original, Ultra, DDA, baseline, freeze and the rest) are defined at the end of USER_GUIDE.md.
The **Reporting Framework** is Blackboard's way to run custom SQL over REST, an alternative runner to
DDA.

## Where it came from

The queries and severity tiers came out of a 2026 Original-to-Ultra conversion engagement and were made
client-neutral for this repo. Run `convscan check` first on any new site.
