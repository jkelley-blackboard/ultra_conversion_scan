# ultra_conversion_scan (`convscan`)

Read-only scans and human-readable reports for converting Blackboard LMS courses from the
Original course view to the Ultra course view. It runs a fixed SQL kit against the reporting
database, saves the results as CSV, applies a rule table, and writes Markdown reports. It needs
no AI and no analyst in the loop: the same data always gives the same report.

**Status:** scaffold, 2026-11-14. The SQL kit was validated on a demo DDA site on 2026-11-13; the
Python around it is new and has only been run against demo.

## What it produces

| Mode | When | Output |
|---|---|---|
| `convscan check` | Once per site | S0 schema check: every table and column the kit uses. Zero rows missing means the kit will run |
| `convscan pre` | Before a batch converts | Per-course **pre-conversion report** (risks by severity, known fixes, items to check), a batch summary, and the saved baseline CSVs |
| `convscan post` | After copy, convert and repairs | Per-course **hand-off report** (what carried over, what didn't, what still needs action), a batch summary and the **ID map** (`idmap.csv`, Original to Ultra course and grade column IDs) |
| `convscan tasks` | During copy and convert | The copy and convert task for each course in a manifest, from the system task table (S13). `--wait` polls every minute until all have finished |
| `convscan render` | Any time | Rebuilds the reports from a saved run, with no database, after editing rules or templates |
| `convscan sql` | Any time | Prints the expanded SQL for one scope, for running through another tool (for example the Reporting Framework) |

## How it works

```
scope (manifest CSV or hierarchy node)
   -> SQL kit (src/convscan/sql/conversion_scan.template.sql), expanded per scope
   -> runner (DDA over psycopg2, read-only session)       -> runs/<name>/data/S*.csv
   -> rules (src/convscan/rules/default.yaml)             -> findings per course
   -> compare (post only: baseline run vs copy run, M2)   -> checks per course, idmap.csv
   -> templates (src/convscan/templates/*.md.j2)          -> runs/<name>/reports/*.md
```

- **The rule table holds the judgment.** Each rule names a query, a filter, a measure and a
  threshold, and carries its severity tier, whether it's a known issue, the plain-language
  wording and the action. Change the YAML to change the reports. See "Writing rules" below.
- **The runner is replaceable.** `runner.py` defines a one-method interface (`query(sql)` returning
  columns and rows). `DdaRunner` is the only implementation today; a Reporting Framework runner
  would slot in beside it without touching rules, compare or templates.
- **The post-scan is a compare.** It reads the pre-scan's saved CSVs as the baseline, scans the
  copies, and compares members, content, columns, groups, release rules, per-learner grades and
  attempts, SCORM runtime state, partial-credit weights and test exceptions.

## Severity tiers

| Tier | Meaning |
|---|---|
| 1 | Blocks a learner resuming or finishing |
| 2 | Must be fixed, but doesn't block learners |
| 3 | Improves the experience |
| 4 | Makes the most of Ultra |
| 0 | Unknown or not testable by SQL: check by hand |

## Install

Python 3.10 or later.

From the repo folder:

```powershell
pip install -e ".[dev]"
python -m pytest
```

That installs `psycopg2-binary`, `PyYAML`, `Jinja2` and pytest. Run the tool as `convscan ...`, or as
`python -m convscan ...` if the Python Scripts folder isn't on `PATH`.

## Connection

Read from environment variables, the same names as the DDA tool (`github/DDA/tools/dda_query.ps1`):

| Variable | Notes |
|---|---|
| `DDA_HOST` | Reporting database host |
| `DDA_PORT` | Default 5432 |
| `DDA_DBNAME` | Site database name |
| `DDA_USER` | Read-only DDA user |
| `DDA_PASSWORD` | Never stored in config or in a run |

The session is opened read-only, and every statement in the kit is a `SELECT`.

## Usage

```powershell
convscan check
convscan pre  --manifest batch01.csv --out runs\2026-12-01_batch01
convscan post --manifest batch01.csv --baseline runs\2026-12-01_batch01 --out runs\2026-12-05_batch01_post
convscan render runs\2026-12-01_batch01
convscan sql  --manifest batch01.csv --scope original > batch01_original.sql
```

**Scope** is either:

- `--manifest file.csv` with columns `orig_course_id,new_course_id` (`new_course_id` may be blank:
  it is then the Original ID plus the configured suffix), or
- `--node <batch_uid>`: every Original associated with that institutional hierarchy node. Copies
  are found by the suffix rule. Tagging each batch's courses to a node (invisible to learners)
  means nobody maintains course lists by hand, and a course that moves batch stays right.

**Options:** `--config file.yaml` (see `config.example.yaml`), `--no-learner` (skip the per-learner
queries S7, S7b, S8b, S10 and S12b for a quick look; the post compare then can't check learner
records), `--suffix` (override the new course ID suffix; `--suffix ""` compares a course with
itself, which is how the tool is smoke-tested on demo).

## Runs and learner data

Each run is a folder:

```
runs/<name>/
  run.json            scope, settings, row counts, timings, errors
  data/S1.csv ...     one CSV per query
  reports/            <course_id>_preflight.md or <course_id>_handoff.md, batch_summary.md, idmap.csv
```

Per-learner queries identify learners by internal key (`users_pk1`) only, never by name, username or
email, but the CSVs are still learner records. **Keep runs out of this repo** (`runs/` is ignored by
Git) and out of shared or client-visible folders unless the institution has agreed. The reports
themselves show counts, not learners.

## Writing rules

```yaml
- id: open_attempts_at_freeze
  title: Test attempts open at the freeze
  source: S12                      # query label
  measure: sum(open_attempts)      # count | sum(col) | max(col) | min(col) | any(col) | distinct(col)
  where: {}                        # optional filters, combined with AND
  threshold: 0                     # fires when measure > threshold
  severity: 1
  known: true
  says: "{value} attempt(s) open in {n} test(s): {examples}"
  action: Tell learners to submit before the freeze, or confirm the attempts carry over.
  examples: test_title             # optional column listed in the finding (first five values)
```

**Filters:** `col: value` (equals; a list means any of), and suffixed forms `col__ne`, `col__gt`,
`col__gte`, `col__lt`, `col__notnull: true`, `col__null: true`, `col__contains`, `col__startswith`.
Values from CSV are compared as numbers or booleans where they parse as such.

**Wording:** `says` can use `{value}` (the measure), `{n}` (matching rows), `{examples}`, and
`{first[col]}` (a column from the first matching row). Client-facing wording rules apply: plain
language, no em-dashes.

If a rule's query wasn't run (for example with `--no-learner`), the report lists the rule under
"Not checked" instead of silently passing it.

## Not checked by this tool

SQL can't see everything. The reports list these as not checked:

- what a learner actually sees and whether SCORM content resumes on screen (use a learner-view
  check, for example Playwright);
- whether files linked from the Content Collection still exist (an HTTP or REST check);
- packages launched from the Content Collection rather than from a SCORM item;
- anything outside the LMS that stores course or column IDs (the ID map is the input for that).

## Layout

```
src/convscan/
  cli.py          command line
  config.py       defaults and YAML config
  scope.py        manifest and hierarchy-node scope SQL
  kit.py          loads the SQL template, expands it, splits it into labeled statements
  runner.py       Runner interface, DdaRunner, run_kit (writes CSVs and run.json), load_run
  rules.py        rule table evaluation
  compare.py      post-scan compare and ID map
  report.py       course facts and report rendering
  sql/            conversion_scan.template.sql (the kit)
  rules/          default.yaml
  templates/      preflight.md.j2, handoff.md.j2, batch_summary.md.j2
tests/            pytest: kit splitting, scope SQL, rules
examples/         manifest.csv
```

## Origin and provenance

The SQL kit and the severity tiers came out of a 2026 Original-to-Ultra conversion engagement and
were made client-neutral for this repo. Code values were confirmed on demo DDA on 2026-11-13; they
are listed in the header of the SQL template. Run `convscan check` first on any new site.

## Open items

- Run `check` and `pre` on a production site; demo has no real conversion copies.
- Reporting Framework runner (whether it accepts the recursive S3b, `md5` and `string_agg`, and the
  size of the per-learner results).
- M1 (item match by title path) is not implemented; the compare matches columns by M2 and counts
  items.
- Word output through the Blackboard brand template.
