# ultra_conversion_scan (`convscan`)

`convscan` checks Blackboard LMS courses before and after they're converted from the Original course
view to the Ultra course view, and writes plain-language reports about what it finds.

It reads the LMS reporting database (read-only), saves what it reads, applies a table of rules, and
writes the reports. There's no AI and no analyst in the loop: the same data always gives the same
report.

**Status (2026-11-14):** working, and tested on four real copy-and-convert runs on a demo site (2 to
10 learners per course). Not yet run on a production site.

## A batch, step by step

| Step | Command | What you get |
|---|---|---|
| 1. Once per site, check the database has everything the queries need | `convscan check` | "every table and column is present", or a list of what's missing |
| 2. Before the batch, scan the Original courses | `convscan pre --manifest batch01.csv --out runs\batch01_pre` | A **pre-conversion report** per course and a batch summary. The saved data becomes the **baseline** |
| 3. At the freeze, make the Originals unavailable and run the bulk copy and convert. Watch it finish | `convscan tasks --manifest batch01.csv --wait` | Each course's copy task, polled every minute until all are done |
| 4. Wait a few minutes for the reporting database to catch up, then scan the copies | `convscan post --manifest batch01.csv --baseline runs\batch01_pre --out runs\batch01_post` | A **hand-off report** per course, a batch summary and the **ID map** |
| 5. Run the repairs (groups, partial credit), then scan the copies again | `convscan post ... --out runs\batch01_post2` | The repaired items should now read "Same" |

Two more commands help along the way:

- `convscan render <run folder>` rebuilds a run's reports from its saved data, with no database. Use it
  after changing the rules or the report templates.
- `convscan sql --manifest batch01.csv --scope original` prints the queries for one set of courses, for
  running through another tool (for example the Reporting Framework).

## Install and connect

Python 3.10 or later. From the repo folder:

```powershell
pip install -e ".[dev]"
python -m pytest
```

This installs `psycopg2-binary`, `PyYAML`, `Jinja2` and pytest. Run the tool as `convscan ...`, or as
`python -m convscan ...` if the Python Scripts folder isn't on `PATH`.

The connection comes from environment variables, the same ones the DDA tool uses
(`github/DDA/tools/dda_query.ps1`):

| Variable | What it is |
|---|---|
| `DDA_HOST` | Reporting database host |
| `DDA_PORT` | Port (default 5432) |
| `DDA_DBNAME` | The site's database name |
| `DDA_USER` | A read-only DDA user |
| `DDA_PASSWORD` | Its password. Never written to a config file or a run |

The session is opened read-only, and every query is a `SELECT`.

## Choosing the courses

Every command except `check` and `render` needs one of these:

- **`--manifest file.csv`**, with columns `orig_course_id,new_course_id`. Leave `new_course_id` blank
  to use the Original ID plus the configured suffix. Example: [examples/manifest.csv](examples/manifest.csv).
- **`--node <batch_uid>`**: every Original course associated with that institutional hierarchy node,
  with copies found by the suffix. Tagging each batch's courses to a node that learners never see
  means nobody keeps course lists by hand, and a course that moves batch is picked up automatically.

**The new course ID.** By default a copy's ID is the Original's plus `-7777`. Blackboard's bulk copy and
convert always puts a hyphen before its suffix (`ECON-101` becomes `ECON-101-SANDBOX`). If copies are
named another way, set `new_id_suffix` in the config or give each `new_course_id` in the manifest.

**Options:**

| Option | Effect |
|---|---|
| `--config file.yaml` | Settings: who the reports are for, the ID suffix, the ID length limit, query timeout. See [config.example.yaml](config.example.yaml) |
| `--no-learner` | Skip the queries that return a row per learner (S7, S8b, S10, S12b). Quicker, but the hand-off can't check learner records |
| `--suffix ""` | Override the suffix. An empty suffix compares each course with itself, which is a quick way to test the tool |

## What the reports say

**Pre-conversion report** (one per course): a short verdict, the course in numbers, a table of risks
(what the scan found, how serious, whether it's a known conversion behavior, and what to do), the
decisions the institution needs to make, the site's conversion settings, and what the scan can't
check.

**Hand-off report** (one per course): the copy task's outcome, then every check comparing the Ultra
copy with the Original's baseline, each marked:

| Result | Meaning |
|---|---|
| Same | Matches the Original |
| Expected | Changed in a way conversion always changes it (for example, the folders it adds) |
| Different | Changed in a way that needs a look |
| Needs action | A known loss to fix before release (for example, groups to restore) |
| Not checked | The data wasn't there to compare |

It ends with the ID map for the course and the site's conversion settings.

**Batch summary**: one line per course with its counts, linking to each report.

**ID map** (`idmap.csv`, with the hand-off): every Original course and grade column ID with its Ultra
counterpart and how it was matched. Systems outside the LMS that store these IDs use it.

**Severity**, in the pre-conversion report:

| Tier | Meaning |
|---|---|
| 1 | Blocks a learner resuming or finishing |
| 2 | Must be fixed, but doesn't block learners |
| 3 | Improves the experience |
| 4 | Makes the most of Ultra |
| 0 | Unknown, or can't be tested by the scan: check by hand |

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
a row per learner and are the large ones.

| Label | What it reads |
|---|---|
| S0 | Every table and column the queries use (`convscan check`) |
| S1 | Course identity, availability, and whether the new ID is free |
| S2 | Members: staff, students in progress, completed and disabled, recent access |
| S3 | Content counts: tests, assignments, SCORM, discussions, LTI, hidden and dated items, Content Collection links |
| S3c | Every content type in the course, with how many items of each are hidden |
| S3b | Every item with its folder path, availability and depth |
| S4 | Grade columns: type, attached item, visibility, calculated or not |
| S5b | Questions with partial credit per course, by how their tests are used (route learners, open the next step, or just graded) |
| S5c | Each partial-credit question's answer values: the repair list and its baseline |
| S5d | Question types in every test, including those Ultra removes |
| S5e | Pools, question banks, and questions drawn into tests by random blocks |
| S6 | SCORM package settings |
| S7 | Per learner: grades and attempts on every column (open, submitted, waiting for grading) |
| S8, S8b | Groups and what uses them; per learner: group membership |
| S9 | Every release condition, with its groups and named learners |
| S10 | Per learner: SCORM attempts and a fingerprint of the saved resume state |
| S11 | Discussion volume |
| S12 | Test settings (time limit, auto-submit, attempts, passwords, proctoring) and open attempts |
| S12b | Per learner or group: test exceptions (extra time or attempts) |
| S13 | System tasks for each course (copy and convert, restore, follow-on tasks) |
| S14 | The site's conversion settings |
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
`{examples}`, and `{first[col]}` (a column from the first matching row). They appear in reports for
the institution, so keep them plain, and don't use em-dashes.

**Thresholds from config:** `threshold: {config: max_course_id_length}` takes the value from the config
file; 0 there switches the rule off.

A rule whose query wasn't run (for example with `--no-learner`) appears under "Not checked" in the
report instead of passing silently.

## Runs and learner data

Each run is a folder:

```
runs/<name>/
  run.json         which courses, settings, rows and seconds per query, any errors
  data/*.csv       one file per query (post-scans add S2_now, S7_now, S10_now: the Originals re-read)
  reports/         the reports, the batch summary, and idmap.csv (post-scan)
```

Learners appear in the data only by internal key (`users_pk1`), never by name, username or email. The
CSVs are still learner records, though. **Keep runs out of this repo** (Git ignores `runs/`) and out of
shared or client-visible folders unless the institution has agreed. The reports show counts, not
learners.

## What it can't check

The reports list these under "Not checked":

- **What a learner actually sees.** The scan proves conditions, groups and scores carried over, not that
  Ultra evaluates them the same way (learning-module sequencing, flattened folders). Pair it with a
  learner-view check, such as the Playwright scripts, on each gated path.
- **Links inside files and packages** (SCORM packages or HTML pages that link to the Original course).
- **Whether linked Content Collection files still exist.**
- **Calculated column values,** which are worked out when displayed, not stored.
- **Systems outside the LMS** that store course or column IDs: give them the ID map.

## Planned work

**Before production:**

- Run `check` and `pre` on a production site, starting with its largest course, and time them.
- Agree the new course ID format with the institution (the hyphen above), and read the site's
  conversion settings with them (S14) before the first batch.

**Gaps found in the demo test:**

- Submitted files, feedback and rubrics aren't compared.
- Test settings are scanned but not compared; assignment settings aren't scanned.
- Group membership after a repair (S8b) and discussion post counts (S11) aren't compared.
- After the partial-credit repair, compare each question's answer values with the baseline, not just
  the count. The repair has to handle Multiple Choice stored as Multiple Answer.
- Calculated column values could be compared through the REST gradebook API.
- Two cheap rules to add: items deeper than the site's nesting limit (S3b has depth, S14 the limit),
  and undeployed tests that other tests draw from, when they'd become question banks.
- Not scanned yet: text grade schemas (Ultra converts them to points) and course menu items (Ultra
  has no course menu).
- Rules that haven't yet fired on real data: test exceptions, open assignment drafts, timed attempts
  open at conversion, learner activity after the pre-scan.

**Scale** (held until production runs are closer). Most courses are small, but a course with
thousands of learners and dozens of graded items (one test course had 8,500 learners and 37 items,
about 315,000 learner rows) is read three times by a post-scan and held in memory. In order of payoff:

1. Compare one fingerprint per course and column (and per SCORM package), computed in the database;
   fetch learner rows only where fingerprints differ.
2. Re-read the Originals only for columns that differ.
3. Scan the largest courses on their own, one at a time, off-peak.
4. Stream results instead of loading them whole, and compress the CSVs.
5. Rewrite the row-by-row counts in S8 as joins.

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
  config.py       defaults and the YAML config
  scope.py        which courses: manifest or hierarchy node
  kit.py          loads the SQL file, fills in the courses, splits it into labeled queries
  runner.py       the database connection, running the queries, saving and loading runs
  scorm.py        decodes SCORM runtime records into fingerprints
  rules.py        applies the rule table
  compare.py      the post-scan compare and the ID map
  report.py       course facts and rendering the reports
  sql/            conversion_scan.template.sql: every query
  rules/          default.yaml: the rule table
  templates/      preflight.md.j2, handoff.md.j2, batch_summary.md.j2
tests/            offline tests (no database needed)
examples/         manifest.csv
```

**Editing the SQL:** queries are separated by a semicolon at the end of a line, so a comment line must
never end in one (a test checks this). Never write a placeholder with its braces in a comment.

## Terms

| Term | Meaning |
|---|---|
| Original, Ultra | The two course views in Blackboard LMS. Conversion moves a course from Original to Ultra |
| Bulk copy and convert | Blackboard's admin tool that copies each course and converts the copy, optionally with learner activity |
| DDA | Direct Data Access: read-only access to the LMS reporting database |
| Reporting Framework | Blackboard's way to run custom SQL over REST, an alternative to DDA |
| Baseline | The pre-scan's saved data, which the post-scan compares against |
| Freeze | The point where an Original course becomes unavailable and is copied |
| Release condition | A rule that controls when learners see an item (for example, after a score on a test) |
| Partial credit | Points for an answer that is partly right |
| SCORM | A standard for packaged e-learning; its player saves each learner's place (the bookmark) |

## Where it came from

The queries and severity tiers came out of a 2026 Original-to-Ultra conversion engagement and were made
client-neutral for this repo. Run `convscan check` first on any new site.
