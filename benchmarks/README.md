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
wagtail-localize and its testing dependencies are installed.

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

## Scope and limitations

- The fixture is deliberately fixed and synthetic. Results describe these
  workloads, not every possible site or content model.
- SQLite keeps local runs cheap and reproducible, but query cost and database
  behavior can differ in production.
- A query count says how many statements ran, not how expensive each statement
  was.
- Timing includes cold Python and framework state for the measured operation;
  it does not model concurrent traffic or warmed application workers.
- Core probes exist only when they isolate a selected optimization that a full
  process would hide. They are not a second catalog of internal functions.
- The harness detects a scaling result but does not attribute its cause. Use
  query inspection or a diagnostic tool for that separate task.

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
```
