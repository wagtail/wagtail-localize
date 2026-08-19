# Performance benchmarks

This directory contains a small benchmark harness for measuring representative
wagtail-localize processes. It reports database query counts and elapsed time
for a fixed synthetic fixture, and verifies that every run completed the
workload it claims to measure.

The harness is intended for reproducible before/after comparisons. It is not an
exhaustive performance suite, a profiler, or a CI performance gate. Use a
profiler or a query-analysis tool to explain a result; use this harness to show
the effect of a change at a stable boundary.

## Running the benchmarks

Run the harness from the repository root in an environment where
wagtail-localize and its testing dependencies are installed, with the project
installed editable (`pip install -e ".[testing]"`). The harness measures the
checkout, but a report's versions come from the installed package's metadata:
a non-editable install can name one version while another is being measured.

List the catalog without setting up Django or creating a database:

```console
python benchmarks/run.py --list
```

Run every size of one flow, one particular size, or the complete catalog:

```console
python benchmarks/run.py edit_translation_get
python benchmarks/run.py edit_translation_get --size small
python benchmarks/run.py all
```

The catalog listing is the authoritative description of the available flows,
their entry points, scale points, and expected workloads. A flow with scale
points runs all of them when `--size` is omitted. A flow without scale points
runs once.

For a comparison that includes timing, repeat each complete execution and
write a machine-readable report:

```console
python benchmarks/run.py all \
    --repeat 5 \
    --json /tmp/wagtail-localize-benchmark.json
```

The JSON file's parent directory must already exist. `--repeat 1` is the
default and is useful while developing a flow; repeated runs are preferable
for results that will be shared.

## Measurement method

The parent process creates a temporary directory and asks a child process to
build an empty migrated SQLite database. For every repetition it then:

1. copies that template database;
2. starts a fresh child process;
3. builds the fixed fixture and runs the flow's setup outside the measurement;
4. measures only the flow's `run` callable;
5. runs verification after measurement has stopped.

There is no warm-up and no state is reused between repetitions. This matters
for mutating operations: running the operation twice against the same database
would measure a different workload on the second pass.

The measured region records elapsed wall-clock time and the number of SQL
queries seen by Django. Verification may query freely because it runs after
the measured region. For scaled flows it also returns the observed workload;
the runner rejects an execution when that value differs from the catalog's
expected workload.

Every repetition of a flow and size must agree on query count, workload unit,
expected workload, and observed workload. A disagreement is reported as a
failed execution rather than averaged away. Elapsed time is summarized as the
median, minimum, and maximum across all repetitions; no observation is
discarded.

The temporary directory and databases are removed when the parent exits. An
internal token prevents the child modes from being pointed at a database the
harness did not create.

## JSON reports and comparisons

`--json` writes schema-versioned provenance alongside the executions:

- UTC run time, Git commit, branch, and working-tree cleanliness;
- Python, Django, Wagtail, and wagtail-localize versions;
- selected flow, size, and repetition count;
- status, query count, expected and observed workload, and timing summary.

A run containing any failed execution is still written, but its top-level
status is `incomplete`. Only a report with `status: complete`, a clean working
tree, matching workloads, and the intended versions should be used as a
baseline.

Query counts are the primary result: compare the same flow and scale point in
equivalent environments, and inspect the small-to-large slope as well as the
absolute totals. Timings are machine-dependent and noisier. Compare timing
with adjacent A and B runs on the same machine, using the same repeat count,
fixture, and dependency versions.

## Explaining a result with Django Query Doctor

The harness says how much work a flow does. It does not say why: a query count
is a total, and a total does not name the loop that produced it.
`run_query_doctor.py` is a separate, manual command for that second question.
It runs a flow from the same catalog, against the same fixture, with the same
process isolation, but inside
[Django Query Doctor](https://pypi.org/project/django-query-doctor/) instead of
inside a stopwatch. What it prints is a diagnosis: N+1 patterns, duplicate
queries, and the call sites they came from.

It is deliberately a second command rather than a flag on the first.
`benchmarks/run.py` does not import Query Doctor, does not know this file
exists, and runs unchanged in an environment where the tool is not installed.
Nothing in CI uses it.

### The optional diagnostic environment

Query Doctor is not a project dependency: nothing in the package, the test
suite, or CI installs or imports it, and it is needed only to run or debug this
benchmark's diagnostic command. Install it into a separate environment, so the
environment the benchmarks run in stays the environment the project declares:

```console
python3 -m venv ~/.venvs/wl-query-doctor
~/.venvs/wl-query-doctor/bin/python -m pip install -e ".[testing]"
~/.venvs/wl-query-doctor/bin/python -m pip install -r benchmarks/requirements-query-doctor.txt
```

The location and name are yours to choose; what matters is that it is a
separate environment and that it does not live inside the checkout. An
untracked directory in the repository would leave `git status` dirty, and with
it the `working_tree_clean` field that decides whether a report can serve as a
baseline.

`benchmarks/requirements-query-doctor.txt` pins the version the harness was
verified against, so a diagnosis run later reproduces the one run today.

Running the diagnostic command from an environment without the tool prints
what is missing and stops before creating a database.

### Running a diagnosis

```console
~/.venvs/wl-query-doctor/bin/python benchmarks/run_query_doctor.py --list
~/.venvs/wl-query-doctor/bin/python benchmarks/run_query_doctor.py core_page_index --size small
~/.venvs/wl-query-doctor/bin/python benchmarks/run_query_doctor.py all
```

Flow names, sizes, and selection rules are the harness's own: `--list` prints
the same catalog, a scaled flow diagnoses every size when `--size` is omitted,
and `all` covers the same executions in the same order. `--list` needs neither
Django nor Query Doctor.

Each execution builds the fixture, runs the flow's `setup`, diagnoses only the
flow's `run`, and then verifies. As in the harness, an execution whose observed
workload differs from the catalog's expected workload fails: a diagnosis of a
scenario that did not build explains something else.

### Reading the output

Output is diagnostic, not a baseline. Query Doctor wraps every cursor and walks
the stack for each query, so its timings include that overhead and are not
comparable with `run.py`'s. Its query total is real, but the numbers that
belong in a before/after comparison are the harness's.

A prescription is a hypothesis with a call site attached, not a verdict. Use it
to find where to look; use `run.py` to show that a change moved the number.

## Attributing a result with the harness itself

`run_attribution.py` answers the same second question from a different angle. A
diagnostic tool inspects one execution and applies a heuristic to decide which
queries look repeated. This command compares the two scale points a flow already
declares and reports which groups of queries grew with the workload. Growth with
the workload is not a sign of the cost this project looks for; it is that cost,
which is why the comparison needs calibrated sizes and cannot be done against a
single run.

It runs the flow's own call in an isolated child process, once per size, with a
`connection.execute_wrapper` installed. Each cursor invocation becomes an event
carrying the statement's normalised shape, the nearest `wagtail_localize` frame
below it, the arity of any `IN` list, and the batch size of an `executemany`.
No parameter value enters an event or the JSON report; the run itself still
holds interpolated SQL in Django's query log while the debug cursor is on.
Events are grouped by shape and frame, and groups are ranked by how fast each
grows per unit of workload:

```console
python benchmarks/run_attribution.py core_page_index
python benchmarks/run_attribution.py submit_page_post --json report.json
```

The unit is the flow, not one execution of it, so the command takes no `--size`
and accepts only a flow declaring exactly two scale points. `--list` prints the
whole catalog, including flows this command cannot attribute; asking for one of
those fails immediately and says why.

The command needs no extra dependency: `execute_wrapper` is Django's own. It is
still separate from `run.py` for the reason `run_query_doctor.py` is separate. A
baseline comes from one stable, minimal counter, and diagnostic instrumentation
never produces one.

### Reading the output

The report opens with a reconciliation, because a report that does not add up to
the number it explains is describing something else:

```
  small   519 queries  = 515 attributed + 4 outside execute_wrapper
```

The gap is not a loss. Django's `_commit()` and `_rollback()` call the database
connection directly and append a synthetic record to the query log, so
`CaptureQueriesContext` counts them and no wrapper can see them. They are real
work with a real cost; they have no call site this command can honestly name, so
it states them instead of dropping them.

Each group then shows its rate, its count at both sizes, and where it ran:

```
  +1.00/indexed_pages   24 -> 64   synctree.py:77 in from_page_instance
```

A rate is the secant between two points, not proof that the growth is linear:
any two points fit a line exactly. Where the two counts imply a non-zero cost at
zero workload, the row also shows that estimate. It is a description of these
two points and nothing more: a positive value can be a genuine fixed cost paid
once, a negative one can mean the group runs for only part of the workload, and
neither reading is available from the two numbers alone.

A group whose shape hides a width carries it as a side note, because a count
cannot show it: `[IN arity 2 -> 40]` is one statement carrying twenty times as
many values, and `[batch …]` is the same for an `executemany`. What that costs
the database is a separate question this harness does not answer; what it shows
is that the statement absorbed work the query count no longer reflects.

Groups that shrank are listed separately, and the tail the report does not print
is summarised with both its net and its gross movement, so churn between two
sizes stays visible even when it cancels out.

Two limits are worth stating. The frame on each row is the nearest
`wagtail_localize` frame still on the stack when the statement ran, which is
neither always where the queryset was built nor always where the SQL came from:
a queryset created in a method and evaluated later in a loop, a template, or a
serialiser is attributed to the evaluation, and SQL issued inside Wagtail or
Django is attributed to the product call that entered them. And a group that
grows with the workload is not by that fact a defect. A flow that creates one
object per page is supposed to cost one insert per page. What the report gives
is a lead, ranked; deciding which leads are legitimate is the reader's.

## Scope and limitations

- The fixture is deliberately fixed and synthetic. Results describe these
  workloads, not every possible site or content model.
- SQLite keeps local runs cheap and reproducible, but query cost and database
  behavior can differ in production.
- A query count is the number of entries in Django's query log, not the number
  of statements the database ran and not a measure of what each one cost: a
  commit is one entry, and so is an `executemany` however many rows it carries.
- Timing includes cold Python and framework state for the measured operation;
  it does not model concurrent traffic or warmed application workers.
- Core probes exist only when they isolate a selected optimization that a full
  process would hide. They are not a second catalog of internal functions.
- `run.py` detects a scaling result but does not attribute its cause. That is a
  separate task, and a separate command: `run_attribution.py` for where a flow's
  own growth comes from, `run_query_doctor.py` for a second opinion from an
  outside tool.

## Changing the catalog

Each `Flow` in `catalog.py` declares its purpose and entry point, plus optional
small and large `ScalePoint` values. Its responsibilities are deliberately
separated:

- `setup` asserts or establishes the pre-measurement scenario;
- `run` performs only the operation being measured;
- `verify` proves the operation happened and returns the observed workload.

Keep fixture construction and verification outside `run`. Prefer properties
such as stable workload and a flat small-to-large query slope over absolute
query-count assertions in product tests. Run the harness tests after changing
the runner, fixture, or catalog:

```console
python testmanage.py test tests.test_benchmarks_harness
python testmanage.py test tests.test_benchmarks_query_doctor
```

Both suites run without Query Doctor installed.
