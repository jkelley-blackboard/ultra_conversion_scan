# convscan User's Guide

For the people who run conversion batches and read the reports. How the tool is built, and how to
change its rules or queries, is in [README.md](README.md).

## What convscan does

convscan is a Python command-line tool that checks Blackboard LMS courses before and after they're
converted from the Original course view to the Ultra course view. It reads the Blackboard LMS database
through the Direct Data Access (DDA) service, and writes plain-language reports about what it finds.
You run it from a terminal: PowerShell on Windows, Terminal on macOS, or any shell on Linux. The
commands in this guide are the same on all three unless a table shows otherwise.

- **Before conversion,** it reads each Original course and reports what's likely to break, how
  serious each risk is, and what to do about it.
- **After conversion,** it compares each Ultra copy with the Original and reports what carried over,
  what changed as expected, and what needs fixing before learners are let in. It also writes an ID
  map from the Original course and grade column IDs to the new ones.

It only reads. Every query is a `SELECT` against the LMS reporting database, through a read-only
session. There's no AI and no analyst in the loop: the same data always gives the same report.

To see what the reports look like before you run anything, open
[examples/sample_reports/](examples/sample_reports/). It has a pre-conversion report, a hand-off report
and an ID map for two invented courses, one with typical losses and one clean.

## Before you start

### Install

You need Python 3.10 or later. From the repo folder:

| | Command |
|---|---|
| Windows | `pip install -e .` |
| macOS, Linux | `pip3 install -e .` (on macOS, Python usually comes from python.org or Homebrew; the system one may be too old) |

Run the tool as `convscan ...`. If your terminal says `convscan` isn't recognized (Windows) or
`command not found` (macOS, Linux), Python's scripts folder isn't on your `PATH`. Use
`python -m convscan ...` on Windows, or `python3 -m convscan ...` on macOS and Linux, which work the
same way.

### Connect

convscan reads the LMS database through Direct Data Access (DDA). You need the site's DDA connection
details and a read-only DDA user, which Blackboard provides with DDA access.

1. Copy [config.example.yaml](config.example.yaml) to a new file for the site, for example
   `config_mysite.yaml`, and fill in the `db:` block:

   ```yaml
   db:
     host: the DDA host name
     port: 5432
     dbname: the site's database name
     user: your read-only DDA user
   prepared_for: Your Institution
   ```

2. Pass the file to every command with `--config`, before the command name:

   ```
   convscan --config config_mysite.yaml check
   ```

3. convscan asks for the DDA password each time it connects. What you type isn't shown, and it isn't
   saved anywhere.

**Don't put the password in the config file:** convscan refuses to run if you do. Config files get
copied and shared, and a password in one is easy to leak.

**To skip the prompt,** for example when running several commands in a row, set the password for the
current terminal window only. It's forgotten when the window closes, and what you type isn't shown:

| | Command |
|---|---|
| Windows (PowerShell 7) | `$env:DDA_PASSWORD = Read-Host "DDA password" -MaskInput` |
| macOS, Linux | `read -s -p "DDA password: " DDA_PASSWORD && export DDA_PASSWORD` |

In the older Windows PowerShell 5.1, which has no `-MaskInput`, just let convscan ask.

Don't save the password permanently: not with `setx` on Windows, which stores it in plain text in your
Windows profile, and not in a shell startup file such as `~/.zshrc` on macOS.

**Environment variables instead of a config file:** `DDA_HOST`, `DDA_PORT`, `DDA_DBNAME` and `DDA_USER`
work too, and override the config file when both are set. That suits a machine set up for one site.

Run `convscan --config config_mysite.yaml check` to test the connection. If it can't connect, it says
which host, database and user it tried, and why.

### Configure (optional)

The same config file holds the other settings. Every setting is optional:

| Setting | Default | What it does |
|---|---|---|
| `db` | none | The connection, above |
| `prepared_for` | `TODO institution name` | The name at the top of every report. Set this |
| `new_id_suffix` | `-7777` | Added to an Original's course ID to find its copy (see "The new course ID") |
| `max_course_id_length` | 15 | Flags new course IDs longer than this (0 switches the check off) |
| `statement_timeout_s` | 900 | How long one query may run before the database stops it |
| `learner_queries` | true | false skips the per-learner queries, like `--no-learner` |
| `max_replica_lag_s` | 300 | `post` won't run while the reporting database trails production by more than this |

## Choosing the courses

Every command except `check` and `render` needs a list of courses, given one of two ways.

**A manifest:** a CSV file with the columns `orig_course_id,new_course_id`, one row per course. Leave
`new_course_id` blank and convscan uses the Original's ID plus the suffix. Copy
[examples/manifest.csv](examples/manifest.csv) to start.

```
orig_course_id,new_course_id
ECON101,
HIST200,HIST200-ULTRA
```

**A hierarchy node:** `--node <batch_uid>` takes every Original course associated with that
institutional hierarchy node, and finds the copies by the suffix. If each batch's courses are tagged
to a node that learners never see, nobody has to keep course lists by hand, and a course that moves to
another batch is picked up automatically.

### The new course ID

Blackboard's bulk copy and convert always puts a hyphen before the suffix you give it: with the suffix
`7777`, `ECON101` becomes `ECON101-7777`. That's why the default suffix is `-7777`. If your copies are
named another way, set `new_id_suffix` in the config, or give each `new_course_id` in the manifest.

Agree the new ID format with the institution before the first batch. Some systems outside the LMS
can't take a hyphen, and the pre-conversion report flags a new ID that's already taken or too long.

## Running a batch

| Step | When | Command |
|---|---|---|
| 1. Check the site | Once per site | `convscan check` |
| 2. Scan the Originals | Before the batch, and again at the freeze | `convscan pre --manifest batch01.csv --out runs/batch01_pre` |
| 3. Watch the copies | During the copy and convert | `convscan tasks --manifest batch01.csv --wait` |
| 4. Scan the copies | When the copies are done | `convscan post --manifest batch01.csv --baseline runs/batch01_pre --out runs/batch01_post` |
| 5. Scan again after repairs | After fixing what the hand-off report lists | `convscan post --manifest batch01.csv --baseline runs/batch01_pre --out runs/batch01_post2` |

Add `--config config_mysite.yaml` before the command name to use your settings, for example
`convscan --config config_mysite.yaml pre ...`. Paths use forward slashes, which work on Windows too.

### 1. Check the site

`convscan check` confirms that every table and column the queries use exists on this site, and shows
how far the reporting database is behind production. If anything is missing, it lists it and stops:
the queries won't run as written on this site.

### 2. Scan the Originals

`convscan pre` writes a **pre-conversion report** for each course and a batch summary. Read the
reports with the institution: they list the decisions to make before the conversion.

The data this scan saves becomes the **baseline** that step 4 compares against. Run it again at the
freeze, once the courses are unavailable and just before the copy starts, so the baseline is as close
as possible to what gets copied. Each run needs a new `--out` folder.

### 3. Run the copy and convert, and watch it

At the freeze, make the Originals unavailable to learners (bulk copy and convert skips available
courses), then start the copy and convert in the LMS. Blackboard runs two conversions at a time.

`convscan tasks --wait` shows each course's copy task every minute until all have finished, then waits
for the reporting database to catch up. When it prints "ready for post", go to step 4.
`--timeout` sets how many minutes it waits in all (120 by default).

### 4. Scan the copies

`convscan post` writes a **hand-off report** for each course, a batch summary and the **ID map**
(`idmap.csv`).

The reporting database is a copy of production that trails it slightly. After a large batch of copies
it can fall further behind, and a scan of half-copied courses would report losses that aren't real.
So `post` checks first and won't run while the database is more than `max_replica_lag_s` behind (300
seconds by default). Wait a few minutes and run it again. `--ignore-lag` runs it anyway, and the
hand-off report then warns that its losses may not be real yet.

### 5. Repair, then scan again

Fix what the hand-off reports mark **Needs action**, then run `post` again into a new folder, against
the same baseline. The repaired items should now read **Same**. Release the course to learners when
the report has no "Needs action" rows left and the institution has checked what the report asks them
to check.

### Other commands

| Command | What it does |
|---|---|
| `convscan render <run folder>` | Rebuilds a run's reports from its saved data, with no database. Use it after the rules or report templates change |
| `convscan sql --manifest batch01.csv --scope original` | Prints the queries for a set of courses (`--scope copy` for the copies), to run through another tool |

### Options

| Option | Effect |
|---|---|
| `--no-learner` | Skips the queries that return a row per learner. Quicker, but the hand-off can't check learner records, and says so |
| `--ignore-lag` | `post` only: runs even while the reporting database is behind |
| `--suffix ""` | Overrides the suffix for this run. An empty suffix compares each course with itself, a quick way to try the tool on any site |

## Reading the reports

Each run folder has a `reports/` folder with one report per course and a `batch_summary.md` that links
to them all.

### The pre-conversion report

1. **In short:** ready or not, the items that would block learners, and how many decisions are needed.
2. **The course:** members, learners in progress and completed, content, gated items, grade columns,
   groups.
3. **What could go wrong:** one row per risk, with how serious it is, whether it's a known conversion
   behavior, what the scan found, and what to do.
4. **Decisions needed:** the risks the institution has to decide on.
5. **Site conversion settings:** site-wide settings that change how every course converts. Agree them
   before the first batch: the additional nesting level can't be undone.
6. **Not checked by this scan:** what to check another way.

**Severity:**

| | Meaning |
|---|---|
| Blocks learners | A learner couldn't resume or finish. Fix before release |
| Needs fixing | Must be fixed, but doesn't stop learners |
| Improves the experience | Worth doing, not required |
| Makes the most of Ultra | An opportunity, not a problem |
| To check | The scan can't tell: check by hand |

A risk marked **known** is a conversion behavior with a known fix (for example, groups aren't carried
over, and there's a script to restore them). One not marked known needs a closer look.

### The hand-off report

It opens with the copy task's outcome, then lists every check comparing the Ultra copy with the
baseline: members, content, availability, grade columns, groups, release conditions, partial credit,
question types and sources, test exceptions, work in progress, every learner's grades and attempts,
and SCORM resume state. Each check is marked:

| Result | Meaning | What to do |
|---|---|---|
| Same | Matches the Original | Nothing |
| Expected | Changed in a way conversion always changes it (the folders it adds, titles losing their formatting) | Nothing |
| Different | Changed in a way that needs a look | Find out why before release |
| Needs action | A known loss (groups to restore, answer values to re-enter) | Repair, then scan again |
| Not checked | The data wasn't there to compare | Check another way, or rerun with the missing queries |

Learner activity after the pre-scan doesn't count as a loss: the post-scan re-reads the Originals, and
a copy that matches either the baseline or the Original as it is now counts as a match.

### The ID map

`idmap.csv` lists every Original course and grade column ID beside its Ultra counterpart, with how it
was matched:

| Status | Meaning |
|---|---|
| `matched` | One column in the copy fits |
| `matched (visibility tie-break)`, `matched (order tie-break)` | Several columns share a title (four "Total" columns, say); paired by visibility, then by creation order |
| `ambiguous` | More than one candidate and no way to choose. Resolve by hand before hand-off |
| `not found` | No column in the copy. Resolve before hand-off |
| `removed in Ultra (weighted total)` | Ultra drops the weighted total column |
| `new in Ultra` | A column only the copy has. Usually safe to ignore |

Give the ID map to any system outside the LMS that stores course or grade column IDs.

## Looking after the data

convscan saves no names, usernames, email addresses or student IDs. Learners appear in the saved data
only as internal database keys, and the reports contain counts only.

Each run is a folder:

```
runs/batch01_post/
  run.json     which courses, settings, rows and seconds per query, replica lag, any errors
  data/        one CSV per query: grade, attempt and SCORM records by internal key
  reports/     the reports, the batch summary, and idmap.csv
```

- **Share the `reports/` folder.** It's what the institution and the project need.
- **Keep `data/` where the scan ran.** It holds grade and attempt records, and for large courses it can
  be large. Delete it once the batch is signed off, unless the project needs it kept.
- **Never commit runs to this repo.** Git ignores `runs/`.

## What convscan can't check

The reports list these under "Not checked":

- **What a learner actually sees.** The scan proves conditions, groups and scores carried over, not
  that Ultra applies them the same way. Check each gated path in a learner view.
- **Links inside SCORM packages and Content Collection pages** that point back to the Original course.
- **Whether linked Content Collection files still exist.**
- **Calculated column values,** which are worked out when displayed, not stored.
- **Systems outside the LMS** that store course or column IDs: give them the ID map.

## When something goes wrong

| Message or symptom | What it means | What to do |
|---|---|---|
| `No database host, dbname, user given` | No connection details were found | Fill in the `db:` block and pass the file with `--config` (see "Connect") |
| `Couldn't connect to ...` | Wrong details or password, or the network can't reach the host | Check the details it prints; check you're on a network allowed to reach DDA |
| `don't put the database password in a config file` | The config file has a `password` line | Delete the line; convscan asks for the password instead |
| `convscan` isn't recognized, or `command not found` | Python's scripts folder isn't on `PATH` | Use `python -m convscan ...` (Windows) or `python3 -m convscan ...` (macOS, Linux) |
| `pip: command not found` on macOS | macOS names it `pip3` | Use `pip3`, or `python3 -m pip` |
| `... already holds a run; choose a new --out folder` | Runs are never overwritten | Give a new `--out` folder |
| `table/column(s) MISSING` from `check` | The site's database differs from what the queries expect | Don't run `pre` or `post` until the queries are updated for this site |
| `the reporting database is more than 300 s behind` | The replica is catching up after the copies | Wait and run `post` again |
| `replica lag: could not read the replica lag` | The DDA user can't see replication status | `post` still runs; check the copies look complete before trusting the losses |
| `no copy task yet` from `tasks` | The copy hasn't started for that course, or the new course ID in the manifest is wrong | Check the copy was started, and the copy's real course ID |
| A query shows an error in the run output, or in `run.json` | It failed or timed out (`statement_timeout_s`) | The checks that need it show as "Not checked". Raise the timeout, or scan large courses on their own |
| Many "Different" rows straight after a copy | The copies may not have finished replicating | Run `post` again into a new folder |

## Terms

| Term | Meaning |
|---|---|
| Original, Ultra | The two course views in Blackboard LMS. Conversion moves a course from Original to Ultra |
| Bulk copy and convert | Blackboard's admin tool that copies each course and converts the copy, optionally with learner activity |
| DDA | Direct Data Access: read-only access to the LMS reporting database, a copy of production that trails it slightly |
| Baseline | The pre-scan's saved data, which the post-scan compares against |
| Freeze | The point where an Original course is made unavailable and copied |
| Release condition | A rule that controls when learners see an item (for example, after a score on a test) |
| Partial credit | Points for an answer that is partly right |
| SCORM | A standard for packaged e-learning. Its player saves each learner's place, so they can resume |
