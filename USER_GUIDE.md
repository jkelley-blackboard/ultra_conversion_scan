# convscan User's Guide

convscan is a Python command-line tool that checks Blackboard LMS courses before and after they're
converted from the Original course view to the Ultra course view. It reads the Blackboard LMS database
through the Direct Data Access (DDA) service and writes plain-language reports.

This guide is for the people who run conversion batches and read the reports. How the tool is built,
and how to change its rules or queries, is in [README.md](README.md).

## Contents

1. [How convscan works](#how-convscan-works): the ideas everything else builds on
2. [Set up](#set-up): install, connect, keep the password safe
3. [Choose the courses](#choose-the-courses): manifests, hierarchy nodes, and the new course ID
4. [Run a batch](#run-a-batch): the five steps, from first scan to release
5. [Read the reports](#read-the-reports): the pre-conversion report, the hand-off report, the ID map
6. [Look after the data](#look-after-the-data): what's saved, where, and for how long
7. [Know the limits](#know-the-limits): what convscan can't check
8. [Troubleshoot](#troubleshoot): messages and what to do
9. [Reference](#reference): commands, options, settings, related resources
10. [Terms](#terms)

To see what the reports look like before you install anything, open
[examples/sample_reports/](examples/sample_reports/): a pre-conversion report, a hand-off report and an
ID map for two invented courses, one with typical losses and one clean.

## How convscan works

Five ideas explain everything convscan does.

**Two scans and a baseline.** A conversion copies each Original course and converts the copy to Ultra.
convscan scans twice. The *pre-scan* reads the Original courses before the copy and reports what's
likely to break. What it saves becomes the *baseline*. The *post-scan* reads the Ultra copies afterward
and compares them with the baseline, item by item and, for learners in progress, learner by learner, to
show what carried over and what didn't.

**It only reads, from a copy of production.** DDA gives read-only access to a replica of the site's
database: a copy that trails production by seconds or minutes. convscan opens a read-only session and
runs only `SELECT` queries, so it can't change anything, and scanning puts no load on the live site.
Because the replica trails production, convscan checks how far behind it is before it compares copies
that were only just made.

**Rules, not judgment.** What counts as a risk, how serious it is, and what to do about it come from a
fixed table of rules, and the comparison knows what conversion always changes (it adds folders, it
strips formatting from titles). There's no AI and no analyst in the loop: the same data always gives
the same report, whoever runs it.

**Each scan is a named run with two folders.** You give every scan a name, such as `batch01_pre`. Its
data, including learner-level records, goes to a local data folder. Its reports go to a reports folder,
which is what you share. Names are never reused, so nothing is overwritten.

**Learners appear only as numbers, and only learners in progress are read one by one.** convscan saves
no names, usernames, email addresses or student IDs. Learners appear in the saved data only as internal
database keys, and the reports contain counts only. Students who are unavailable (they've completed,
or their access has expired) or disabled can't resume, so by default their records are counted, not read: the
copy keeps them, and the hand-off compares the totals.

## Set up

You set up convscan once per computer, and connect it once per site. A *config file* holds the site's
connection details and your preferences, so you don't retype them for every command. The one thing it
never holds is the password.

### Install

You need Python 3.10 or later. From the repo folder:

| | Command |
|---|---|
| Windows | `pip install -e .` |
| macOS, Linux | `pip3 install -e .` (on macOS, use Python from python.org or Homebrew; the built-in one may be too old) |

Then check it runs:

```
convscan --version
```

If your terminal says `convscan` isn't recognized (Windows) or `command not found` (macOS, Linux),
Python's scripts folder isn't on your `PATH`. Use `python -m convscan` (Windows) or `python3 -m convscan`
(macOS, Linux) wherever this guide says `convscan`; it works the same way.

The commands in this guide are the same on Windows, macOS and Linux unless a table shows otherwise.
Paths use forward slashes, which work on Windows too.

### Connect to a site

You need the site's DDA connection details and a read-only DDA user, which Blackboard provides with DDA
access. New to DDA? The [DDA Resource Guide](https://jkelley-blackboard.github.io/DDA/) explains the
service, how to connect, and the database schema.

The data belongs to the institution, so get its written permission before you set up access or scan.
Ask before a DDA user account is created for you, before your IP address is added to the site's DDA
allow list (DDA accepts connections only from listed addresses), and before you extract any data. Say
that the scans save learner-level records by internal key, kept on your computer and deleted at
sign-off (see [Look after the data](#look-after-the-data)).

1. Run `convscan init`. It asks for the host, port, database name, user and the institution's name, and
   writes them to `~/convscan/config.yaml` in your home folder. Leave anything you don't know blank and
   fill it in later; the file is plain text.
2. Run `convscan check`. convscan finds the config by itself, asks for the DDA password, and tests the
   connection.
3. Type the password when asked. What you type isn't shown, and it isn't saved anywhere.

If `check` can't connect, it says which host, database and user it tried, and why.

### Keep the password out of files

A config file gets copied, emailed and attached to tickets, so it's the wrong place for a password.
convscan refuses to run if a config file contains one, and asks for the password each time instead.

To avoid typing it for every command, set it for the current terminal window only. It's forgotten when
the window closes:

| | Command |
|---|---|
| Windows (PowerShell 7) | `$env:DDA_PASSWORD = Read-Host "DDA password" -MaskInput` |
| macOS, Linux | `read -s -p "DDA password: " DDA_PASSWORD && export DDA_PASSWORD` |

In the older Windows PowerShell 5.1, which has no `-MaskInput`, let convscan ask. Don't save the
password permanently: not with `setx` on Windows, which stores it in plain text in your Windows profile,
and not in a shell startup file such as `~/.zshrc` on macOS.

### Work with more than one site

Give each site its own config, and say which one to use:

```
convscan init config_mysite.yaml
convscan --config config_mysite.yaml check
```

`--config` always goes before the command name. Without it, convscan looks for a config in this order
and says which one it used: the `CONVSCAN_CONFIG` environment variable, `convscan.yaml` in the current
folder, then `~/convscan/config.yaml`. Every setting is listed in [Reference](#settings).

## Choose the courses

A *batch* is the set of courses converted together. Every scan works on one batch, and you tell convscan
which courses are in it in one of two ways. It also needs to know each copy's course ID, so it can pair
every Original with its Ultra copy.

### List them in a manifest

A manifest is a CSV file with one row per course:

```
orig_course_id,new_course_id
ECON101,
HIST200,HIST200-ULTRA
```

Leave `new_course_id` blank and convscan uses the Original's ID with the prefix and suffix (next section). Copy
[examples/manifest.csv](examples/manifest.csv) to start, and pass it with `--manifest batch01.csv`.

### Or tag them to a hierarchy node

`--node <batch_uid>` takes every Original course associated with that institutional hierarchy node. If
each batch's courses are tagged to a node that learners never see, nobody has to keep course lists by
hand, and a course that moves to another batch is picked up automatically.

### Agree the new course ID

Blackboard's bulk copy and convert names each copy by adding text to the Original's ID, either after it
(a suffix) or before it (a prefix), and always puts a hyphen between the two: with the suffix `7777`,
`ECON101` becomes `ECON101-7777`, and with the prefix `ULTRA-`, it becomes `ULTRA-ECON101`.

convscan finds each copy as prefix + Original ID + suffix, with the hyphen included in whichever you
set. The defaults are no prefix and the suffix `-7777`. For prefixed copies, set `new_id_prefix: "ULTRA-"`
and `new_id_suffix: ""` in the config, or use `--prefix ULTRA- --suffix ""` for one run. A manifest row's
`new_course_id`, when filled in, always wins.

Agree the format with the institution before the first batch. Some systems outside the LMS can't take a
hyphen, and the pre-conversion report flags a new ID that's already taken or too long.

## Run a batch

A batch follows a fixed cycle around the *freeze*: the moment the Original courses are made unavailable
and copied. You scan before the freeze to plan, at the freeze to set the baseline, after the copy to
check it, and again after repairs. A course is released to learners only when its hand-off report is
clear.

```
before the batch    at the freeze                        after the copy                      release
     pre       ->   pre (baseline) -> copy and convert -> post -> repair -> post again   ->  learners in
```

| Step | When | Command |
|---|---|---|
| 1. Check the site | Once per site | `convscan check` |
| 2. Scan the Originals | Before the batch, and again at the freeze | `convscan pre --manifest batch01.csv --out batch01_pre` |
| 3. Copy, and watch it | At the freeze | `convscan tasks --manifest batch01.csv --wait` |
| 4. Scan the copies | When the copies are done | `convscan post --manifest batch01.csv --baseline batch01_pre --out batch01_post` |
| 5. Repair, then scan again | After fixing what the hand-off report lists | `convscan post --manifest batch01.csv --baseline batch01_pre --out batch01_post2` |

`--out` names the run; `--baseline` names the pre-scan to compare against.

### 1. Check the site

Every site's database should have the tables and columns convscan reads, but it's worth confirming
before the first batch. `convscan check` tests the connection, confirms every table and column exists,
and shows how far the replica is behind production. If anything is missing, it lists it and stops: the
queries won't run as written on that site.

### 2. Scan the Originals

The pre-scan has two jobs. Before the batch, its **pre-conversion reports** are for planning: read them
with the institution, because they list the decisions to make before the conversion. At the freeze, it
sets the **baseline** that step 4 compares against.

```
convscan pre --manifest batch01.csv --out batch01_pre
```

Run it again at the freeze, once the courses are unavailable and just before the copy starts, under a
new name such as `batch01_freeze`. That baseline is as close as possible to what gets copied; use its
name as `--baseline` in step 4.

The pre-scan reads each learner's grades, attempts and SCORM progress only for students in progress.
For unavailable and disabled students it saves totals per course. The conversion copies every
membership the same way, so the learners in progress show whether records carry over, and the totals
catch anything lost for the rest. If the hand-off shows a difference in those totals, scan the Original
again with `--all-learners` to see whose records are affected. The post-scan always reads the same
learners its baseline read.

### 3. Run the copy and convert, and watch it

The copy itself happens in the LMS, not in convscan. Make the Originals unavailable to learners first:
bulk copy and convert skips courses that are available. Then start the copy and convert. Blackboard
runs two conversions at a time, so a large batch takes a while.

```
convscan tasks --manifest batch01.csv --wait
```

This shows each course's copy task every minute until all have finished, then waits for the replica to
catch up. When it prints "ready for post", go to step 4. `--timeout` sets how many minutes it waits in
all (120 by default).

### 4. Scan the copies

The post-scan compares each Ultra copy with the baseline and writes a **hand-off report** for each
course, a batch summary and the **ID map** (`idmap.csv`).

```
convscan post --manifest batch01.csv --baseline batch01_pre --out batch01_post
```

A large batch of copies is a lot of new data, and the replica can fall further behind than usual while
it catches up. A scan of half-copied courses would report losses that aren't real, so `post` won't run
while the replica is more than 300 seconds behind (`max_replica_lag_s`). Wait a few minutes and run it
again. `--ignore-lag` runs it anyway, and the hand-off report then warns that its losses may not be real
yet.

### 5. Repair, then scan again

Some losses are known and have known fixes, such as restoring groups or re-entering partial-credit
answer values. The hand-off report marks them **Needs action**. Fix them, then run `post` again under a
new name, against the same baseline. The repaired items should now read **Same**.

Release a course to learners when its report has no "Needs action" rows left and the institution has
checked what the report asks them to check.

## Read the reports

Each report answers a different question for a different reader. The **pre-conversion report** asks
"what will go wrong if we convert this course?", for planning with the institution. The **hand-off
report** asks "did this copy come through, and what's left to fix?", for deciding when to release. The
**ID map** answers "what are the new IDs?", for systems outside the LMS. Each run's reports folder also
has a `batch_summary.md` with one line per course, linking to each report.

### The pre-conversion report

It reads top to bottom, from verdict to detail:

1. **In short:** ready or not, the items that would block learners, and how many decisions are needed.
2. **The course:** members, learners in progress, completed or expired, and disabled, content, gated
   items, grade columns, groups.
3. **What could go wrong:** one row per risk, with how serious it is, whether it's a known conversion
   behavior, what the scan found, and what to do.
4. **Decisions needed:** the risks the institution has to decide on.
5. **Site conversion settings:** site-wide settings that change how every course converts. Agree them
   before the first batch: the additional nesting level can't be undone.
6. **Not checked by this scan:** what to check another way.

Each risk has a severity:

| Severity | Meaning |
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
question types and sources, test exceptions, work in progress, the grades and attempts of every learner
in progress, their SCORM resume state, and totals for unavailable and disabled students. Each check has
a result:

| Result | Meaning | What to do |
|---|---|---|
| Same | Matches the Original | Nothing |
| Expected | Changed in a way conversion always changes it (the folders it adds, titles losing their formatting) | Nothing |
| Different | Changed in a way that needs a look | Find out why before release |
| Needs action | A known loss (groups to restore, answer values to re-enter) | Repair, then scan again |
| Not checked | The data wasn't there to compare | Check another way, or rerun with the missing queries |

Learners may keep working in the Originals after the pre-scan. That isn't counted as a loss: the
post-scan re-reads the Originals, and a copy that matches either the baseline or the Original as it is
now counts as a match. The same goes for a learner whose access ends or is extended between the scans:
the post-scan still compares the learners its baseline read.

### The ID map

Conversion gives every course and grade column a new ID. Systems outside the LMS that store those IDs
(a student records system, a certification platform) need the new ones. `idmap.csv` lists every
Original course and grade column ID beside its Ultra counterpart, with how it was matched:

| Status | Meaning |
|---|---|
| `matched` | One column in the copy fits |
| `matched (visibility tie-break)`, `matched (order tie-break)` | Several columns share a title (four "Total" columns, say); paired by visibility, then by creation order |
| `ambiguous` | More than one candidate and no way to choose. Resolve by hand before hand-off |
| `not found` | No column in the copy. Resolve before hand-off |
| `removed in Ultra (weighted total)` | Ultra drops the weighted total column |
| `new in Ultra` | A column only the copy has. Usually safe to ignore |

## Look after the data

Reports and data have different audiences, so they live apart. Reports are for sharing. The data holds
grade, attempt and SCORM records for every learner in progress (every enabled learner with
`--all-learners`), by internal key, and it stays on the computer that ran the scan until the batch is
signed off.

Each run writes two folders:

```
~/convscan/data/batch01_post/       data_dir: stays on this computer
  run.json     which courses, settings, rows and seconds per query, replica lag, any errors
  data/        one CSV per query: grade, attempt and SCORM records by internal key

~/convscan/reports/batch01_post/    reports_dir: what gets shared
  *_handoff.md, batch_summary.md, idmap.csv
  run.json     a copy, so a report can be traced to its run (no learner data in it)
```

- **Share the reports folder.** If reports are shared through a shared folder or a reports repository,
  set `reports_dir` to it and they land there directly.
- **Keep the data folder local.** convscan warns if `data_dir` is inside a synced folder (OneDrive,
  Dropbox, Google Drive, iCloud, Box) or a Git repository.
- **Delete a batch's data once it's signed off,** unless the project needs it kept. `convscan render`
  can rebuild reports only while the data exists.

## Know the limits

convscan proves that the data carried over: conditions, groups, grades, attempts and SCORM progress
match. That isn't quite the same as proving learners get the same experience, and some things don't
live in the database at all. The reports list these under "Not checked":

- **What a learner actually sees.** Ultra may apply the same conditions differently (learning-module
  sequencing, flattened folders). Check each gated path in a learner view.
- **Links inside SCORM packages and Content Collection pages** that point back to the Original course.
- **Whether linked Content Collection files still exist.**
- **Calculated column values,** which are worked out when displayed, not stored.
- **Each record of unavailable and disabled students,** by default: they're compared as totals.
  A difference in the totals says something was lost, not whose; rerun with `--all-learners` to find out.
- **Systems outside the LMS** that store course or column IDs: give them the ID map.

## Troubleshoot

Most problems show up at one of three moments: setting up, scanning, or reading the results.

**Setting up**

| Message or symptom | What it means | What to do |
|---|---|---|
| `convscan` isn't recognized, or `command not found` | Python's scripts folder isn't on `PATH` | Use `python -m convscan` (Windows) or `python3 -m convscan` (macOS, Linux) |
| `pip: command not found` on macOS | macOS names it `pip3` | Use `pip3`, or `python3 -m pip` |
| `No database host, dbname, user given` | No config was found, or it has no connection details | Run `convscan init`, or fill in the `db:` block of your config |
| `Couldn't connect to ...` | Wrong details or password, or the network can't reach the host | Check the details it prints, and that you're on a network allowed to reach DDA |
| `don't put the database password in a config file` | The config file has a `password` line | Delete the line; convscan asks for the password instead |
| `table/column(s) MISSING` from `check` | The site's database differs from what the queries expect | Don't run `pre` or `post` until the queries are updated for this site |

**Scanning**

| Message or symptom | What it means | What to do |
|---|---|---|
| `... already holds a run` or `... already holds reports` | Runs are never overwritten | Give a new `--out` name |
| `WARNING: learner-level data will be written to ...` | `data_dir` is in a synced folder or a Git repository | Set `data_dir` in your config to a local folder |
| `no pre-scan run at ...` | `--baseline` doesn't name a pre-scan | Use the pre-scan's `--out` name, with the same config |
| `no copy task yet` from `tasks` | The copy hasn't started for that course, or the new course ID is wrong | Check the copy was started, and the copy's real course ID |
| `the reporting database is more than 300 s behind` | The replica is catching up after the copies | Wait and run `post` again |
| `replica lag: could not read the replica lag` | The DDA user can't see replication status | `post` still runs; check the copies look complete before trusting the losses |
| A query shows `ERROR` in the run output | It failed or timed out (`statement_timeout_s`) | Its checks show as "Not checked". Raise the timeout, or scan large courses on their own |

**Reading the results**

| Message or symptom | What it means | What to do |
|---|---|---|
| Many "Different" rows straight after a copy | The copies may not have finished replicating | Run `post` again under a new name |
| "Not checked" on learner records | The scan ran with `--no-learner`, or a learner query failed | Rerun without `--no-learner` |
| "Different" on unavailable or disabled students' records | Their totals differ between the Original and the copy | Scan the Original again with `pre --all-learners`, then `post` against that scan, to see whose records |
| A course is missing from the reports | Its ID in the manifest doesn't exist on the site | Check the course ID |

When you ask for help with a report, include `convscan --version` and the run's `run.json` (it holds no
learner data).

## Reference

### Commands

| Command | What it does |
|---|---|
| `convscan init [file]` | Writes a starter config, asking for the connection details. Never overwrites |
| `convscan check` | Tests the connection, the schema and the replica lag |
| `convscan pre --manifest <csv> --out <name>` | Scans the Originals; writes pre-conversion reports and saves the baseline |
| `convscan tasks --manifest <csv> [--wait]` | Shows each course's copy task; `--wait` polls until all finish and the replica catches up |
| `convscan post --manifest <csv> --baseline <name> --out <name>` | Scans the copies, compares with the baseline, writes hand-off reports and the ID map |
| `convscan render <name>` | Rebuilds a run's reports from its saved data, with no database. Use it after the rules or templates change |
| `convscan sql --manifest <csv> [--scope copy]` | Prints the queries for a set of courses, to run through another tool |
| `convscan --version` | Shows the version |

`--node <batch_uid>` can replace `--manifest <csv>` in `pre`, `post` and `sql`. `tasks` needs a
manifest, because a node has no list of copies until they exist. A folder path also
works in place of a run name; data and reports then stay together in that folder.

### Options

| Option | Effect |
|---|---|
| `--config <file>` | The config to use. Goes before the command name |
| `--no-learner` | Skips the queries that return a row per learner. Quicker, but the hand-off can't check learner records, and says so |
| `--all-learners` | `pre` and `sql` only: reads every enabled student's records one by one, not only students in progress. `post` follows its baseline |
| `--ignore-lag` | `post` only: runs even while the replica is behind |
| `--no-students` | `post` and `render`: the copies were made without user activity. Student counts, learner records (grades and attempts, work in progress, SCORM resume state) and unavailable or disabled students' records that stay in the Original show as Expected instead of Different, as long as the copy has none; the non-student members kept are counted. On `render` it marks an existing post-scan run |
| `--no-reread` | `post` only: doesn't read the Originals again, and compares with the baseline alone. Quicker, but a change to an Original after the pre-scan (a new enrollment, a learner's work) shows as Different rather than Expected |
| `--suffix <text>` | Overrides the new-ID suffix for this run. `--suffix ""` (with no prefix) compares each course with itself, a quick way to try the tool on any site |
| `--prefix <text>` | Overrides the new-ID prefix for this run, for example `--prefix ULTRA- --suffix ""` |
| `--timeout <minutes>` | `tasks --wait` only: how long to wait (120 by default) |

### Settings

All optional. [config.example.yaml](config.example.yaml) has them all, with comments. Relative paths are
read from the config file's folder.

| Setting | Default | What it does |
|---|---|---|
| `db` | none | The connection: `host`, `port` (5432), `dbname`, `user`. Never the password |
| `data_dir` | `~/convscan/data` | Where each run's data goes. Keep it local |
| `reports_dir` | `~/convscan/reports` | Where each run's reports go |
| `prepared_for` | `TODO institution name` | The name at the top of every report |
| `new_id_prefix` | `""` (none) | Put before an Original's course ID to find its copy |
| `new_id_suffix` | `-7777` | Added after an Original's course ID to find its copy |
| `max_course_id_length` | 15 | Flags new course IDs longer than this (0 switches the check off) |
| `statement_timeout_s` | 900 | How long one query may run before the database stops it |
| `learner_queries` | true | false skips the per-learner queries, like `--no-learner` |
| `max_replica_lag_s` | 300 | `post` won't run while the replica trails production by more than this |
| `nesting_what_if` | true | The nesting finding says how many folders would still move with the additional nesting level, and marks it a decision. Set false once the site's setting has been decided. Takes effect on `render` too |

### Environment variables

| Variable | What it does |
|---|---|
| `DDA_PASSWORD` | The DDA password, so convscan doesn't ask. Set it per terminal window only |
| `DDA_HOST`, `DDA_PORT`, `DDA_DBNAME`, `DDA_USER` | Override the config's `db` settings |
| `CONVSCAN_CONFIG` | The config to use when `--config` isn't given |

### Related resources

| Resource | What it's for |
|---|---|
| [DDA Resource Guide](https://jkelley-blackboard.github.io/DDA/) | Direct Data Access explained: connecting, the schema explorer, and guides |
| [DDA repository](https://github.com/jkelley-blackboard/DDA) | A library of ready-to-use DDA SQL, the machine-readable schema, and tools. Useful for checking a table or column that `convscan check` reports missing |

## Terms

| Term | Meaning |
|---|---|
| Original, Ultra | The two course views in Blackboard LMS. Conversion moves a course from Original to Ultra |
| Bulk copy and convert | Blackboard's admin tool that copies each course and converts the copy, optionally with learner activity |
| DDA | Direct Data Access: read-only access to a replica of the site's database |
| Replica | A copy of the production database that trails it by seconds or minutes |
| Batch | The set of courses converted together |
| Freeze | The moment an Original course is made unavailable and copied |
| Baseline | The pre-scan's saved data, which the post-scan compares against |
| In progress | A student whose membership is enabled and available: they can still open the course and resume |
| Unavailable | A membership whose learner has completed, or whose access has expired. The copy keeps it; the scan counts its records |
| Run | One scan, under a name, with a data folder and a reports folder |
| Release condition | A rule that controls when learners see an item (for example, after a score on a test) |
| Partial credit | Points for an answer that is partly right |
| SCORM | A standard for packaged e-learning. Its player saves each learner's place, so they can resume |
