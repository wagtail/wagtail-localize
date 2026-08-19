"""Attribute a benchmark flow's query count to the code that produced it.

    python benchmarks/run_attribution.py core_page_index
    python benchmarks/run_attribution.py submit_page_post --json report.json
    python benchmarks/run_attribution.py --list

benchmarks/run.py says how much work a flow does. It cannot say where that work
came from: its measured region is one block, and a total does not name the loop
inside it. This command answers the second question for a flow with two scale
points, by running both sizes and reporting which groups of queries grew with
the workload.

Growth with the workload is not a heuristic for an N+1: it is the definition of
the cost this project is looking for. That is why this command needs the
harness's calibrated sizes and cannot be replaced by a general-purpose detector
running against a single execution.

Like run_query_doctor.py this is a manual diagnostic command, separate from
run.py on purpose. The rule is not that run.py installs nothing -- it already
enables Django's debug cursor through CaptureQueriesContext -- but that a
baseline is produced by one stable, minimal counter, and diagnostic
instrumentation never produces one.

What it reports is a lead for a person to follow. Some queries grow with the
workload because the work does: a flow that creates one object per page is
supposed to cost one insert per page. Nothing here can tell those apart from a
defect, and it does not try to.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile


if __name__ == "__main__":
    # Same reason as in run.py: run as a script this file's directory is on
    # sys.path, not the repo root, and `benchmarks.*` has to resolve to the one
    # package everything else already loaded.
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)


from benchmarks import run


CHILD_FLAG = "--attribute-in-child"
EVENTS_ENV_VAR = "WAGTAIL_LOCALIZE_ATTRIBUTION_EVENTS"

# How many product frames an event carries. The nearest one is the default
# grouping key; the rest are kept so a caller can be identified later without
# measuring again.
STACK_DEPTH = 5

# How far up the stack to look for a product frame before giving up. Deep
# rendering and serialisation stacks are the reason this is not smaller.
STACK_LIMIT = 80

# Groups shown before the tail is summarised, expressed as a share of the total
# absolute movement between the two sizes. Ranking decides what matters; this
# only decides where a long report stops.
COVERAGE = 0.95

# Constant groups listed under the drivers, as the fixed cost of the flow.
FIXED_SHOWN = 10

# Distinct callers kept per group in the JSON report. The report itself shows
# one line of product code; this is what a reader needs to ask who reached it.
CALLERS = 5


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------

# A parenthesised placeholder list belonging to IN / NOT IN. Restricted to IN on
# purpose: collapsing every placeholder run would also merge INSERT ... VALUES
# lists of different widths, which are different statements.
_IN_LIST = re.compile(r"\b(NOT\s+IN|IN)\s*\(\s*%s(?:\s*,\s*%s)*\s*\)", re.IGNORECASE)

# Savepoint identifiers are generated per savepoint, so they would give every
# savepoint its own shape.
_SAVEPOINT_NAME = re.compile(
    r"\b(SAVEPOINT|RELEASE(?:\s+SAVEPOINT)?|ROLLBACK\s+TO(?:\s+SAVEPOINT)?)\s+\S+",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s+")


def in_arity(sql):
    """How many placeholders the statement's IN lists hold, or None.

    Kept beside the shape rather than inside it: a query batching 2 keys and the
    same query batching 40 are one family whose width is worth seeing.
    """
    widths = [match.group(0).count("%s") for match in _IN_LIST.finditer(sql)]
    return sum(widths) if widths else None


def shape(sql):
    """Collapse a statement to the form it shares with its repetitions.

    Only known-volatile syntax is normalised. In particular numeric literals are
    left alone: Django inlines structural numbers such as LIMIT 1 versus
    LIMIT 21, and merging those would conflate .get(), .exists() and pagination.
    Parameters never reach here -- execute_wrapper receives the statement before
    interpolation -- so no value is being hidden by this.
    """
    collapsed = _WHITESPACE.sub(" ", sql).strip()
    collapsed = _IN_LIST.sub(lambda m: f"{m.group(1).upper()} (%s, ...)", collapsed)
    collapsed = _SAVEPOINT_NAME.sub(lambda m: m.group(1).upper(), collapsed)
    return collapsed


def batch_size(params, many):
    """How many parameter sets an executemany carried, when that is knowable.

    DB-API allows an iterable without __len__, and consuming one here to count
    it would empty it before the driver ever saw it. An unknown size is reported
    as unknown rather than paid for.
    """
    if not many or params is None:
        return None
    try:
        return len(params)
    except TypeError:
        return None


def kind(sql):
    """Transaction control, savepoint, or a plain statement.

    ROLLBACK TO SAVEPOINT undoes part of a transaction and ROLLBACK undoes all
    of it, so they are not the same event even though they share a first word.
    """
    head = sql.lstrip()[:24].upper()
    # ROLLBACK TO is tested first: it undoes part of a transaction, where a bare
    # ROLLBACK undoes all of it.
    if head.startswith(("SAVEPOINT", "RELEASE", "ROLLBACK TO")):
        return "savepoint"
    if head.startswith(("BEGIN", "COMMIT", "ROLLBACK")):
        return "transaction"
    return "query"


# ---------------------------------------------------------------------------
# Stacks
# ---------------------------------------------------------------------------

_PRODUCT = f"{os.sep}wagtail_localize{os.sep}"
_HARNESS = f"{os.sep}benchmarks{os.sep}"

OUTSIDE = "<outside wagtail_localize>"


def product_stack():
    """The product frames below this call, nearest first.

    "Nearest product frame" is where the statement was executed, which is not
    always where its queryset was built: a queryset created in one method and
    evaluated in a loop, a template, or a serialiser is attributed to the
    evaluation. The frames above it are kept for that reason.
    """
    frames = []
    frame = sys._getframe(1)
    depth = 0
    while frame is not None and depth < STACK_LIMIT and len(frames) < STACK_DEPTH:
        path = frame.f_code.co_filename
        if _PRODUCT in path and _HARNESS not in path:
            module = path.split(_PRODUCT, 1)[1]
            frames.append(f"{module}:{frame.f_lineno} in {frame.f_code.co_name}")
        frame = frame.f_back
        depth += 1
    return frames


# ---------------------------------------------------------------------------
# Child: one execution, instrumented
# ---------------------------------------------------------------------------


def attribute_in_child(name, size):
    """Run one execution, record an event per cursor invocation, write them out.

    The instrumented region is exactly the flow's own call, the same region
    run.py measures, so the two describe the same work. CaptureQueriesContext
    wraps the execute_wrapper rather than replacing it: it is the harness's
    counter and therefore the authoritative total, while the wrapper is what can
    see a statement's shape and stack.
    """
    run.guard_database()
    catalog, flow, point = run._select(name, size)

    from benchmarks.env import bootstrap

    bootstrap()

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    ctx = catalog.prepare()
    if flow.setup:
        flow.setup(ctx, size)

    events = []

    def record(execute, sql, params, many, context):
        events.append(
            {
                "shape": shape(sql),
                "kind": kind(sql),
                "stack": product_stack(),
                "in_arity": in_arity(sql),
                "batch": batch_size(params, many),
            }
        )
        return execute(sql, params, many, context)

    with (
        CaptureQueriesContext(connection) as captured,
        connection.execute_wrapper(record),
    ):
        artifacts = flow.run(ctx, size)

    observed = flow.verify(ctx, size, artifacts)

    # The same rule the harness applies: attributing a scenario that did not
    # build would explain something else.
    if point is not None and observed != point.expected_workload:
        raise SystemExit(
            f"{name} [{size}] produced {observed} {flow.workload_unit}, but the "
            f"scale point declares {point.expected_workload}. The fixture is not "
            f"building the scenario this size is supposed to explain."
        )

    with open(os.environ[EVENTS_ENV_VAR], "w", encoding="utf-8") as handle:
        json.dump(
            {
                "size": size,
                "observed_workload": observed,
                "total": len(captured),
                "events": events,
            },
            handle,
        )


# ---------------------------------------------------------------------------
# Grouping and reconciliation
# ---------------------------------------------------------------------------


def _span(values):
    """The range a group's events covered, or None if none carried the value."""
    seen = [value for value in values if value is not None]
    if not seen:
        return None
    return [min(seen), max(seen)]


def group(execution):
    """Collapse an execution's events into one entry per (shape, nearest frame).

    Arity and batch size stay out of the key and are reported as the range the
    group covered: a query batching 2 keys and the same query batching 40 are
    one family whose width is what makes the batching visible.
    """
    grouped = {}
    for event in execution["events"]:
        key = (event["shape"], event["stack"][0] if event["stack"] else OUTSIDE)
        entry = grouped.setdefault(
            key, {"count": 0, "kind": event["kind"], "in_arity": [], "batch": []}
        )
        entry["count"] += 1
        entry["in_arity"].append(event["in_arity"])
        entry["batch"].append(event["batch"])
        # The frames above the nearest one, kept per distinct caller. A group is
        # one line of product code; who reaches it is the next question a reader
        # asks, and answering it from the report costs nothing extra to record.
        caller = " <- ".join(event["stack"][1:]) or OUTSIDE
        entry.setdefault("callers", {})
        entry["callers"][caller] = entry["callers"].get(caller, 0) + 1

    return {
        key: {
            "count": entry["count"],
            "kind": entry["kind"],
            "in_arity": _span(entry["in_arity"]),
            "batch": _span(entry["batch"]),
            "callers": dict(
                sorted(entry["callers"].items(), key=lambda item: -item[1])[:CALLERS]
            ),
        }
        for key, entry in grouped.items()
    }


def unattributed(execution):
    """Statements the harness counted that the wrapper could not see.

    Django's _commit() and _rollback() call the database connection directly and
    append a synthetic record to the query log, so CaptureQueriesContext counts
    them and execute_wrapper never runs. They are real work with a real cost;
    they simply have no call site this command can honestly name.
    """
    return execution["total"] - len(execution["events"])


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def build(small_exec, large_exec):
    """Everything the report and the JSON artifact are derived from."""
    small = group(small_exec)
    large = group(large_exec)
    span = large_exec["observed_workload"] - small_exec["observed_workload"]

    empty = {
        "count": 0,
        "kind": None,
        "in_arity": None,
        "batch": None,
        "callers": {},
    }
    rows = []
    for key in set(small) | set(large):
        in_small = small.get(key, empty)
        in_large = large.get(key, empty)
        a = in_small["count"]
        b = in_large["count"]
        rate = (b - a) / span
        rows.append(
            {
                "shape": key[0],
                "frame": key[1],
                "small": a,
                "large": b,
                "delta": b - a,
                "rate": rate,
                # What the two counts imply at zero workload. A summary of these
                # two points, not evidence of linearity: any two points fit a
                # line exactly, and the zero-workload end may describe a state
                # the flow never reaches.
                "fixed": a - rate * small_exec["observed_workload"],
                "kind": in_large["kind"] or in_small["kind"],
                "in_arity": {
                    "small": in_small["in_arity"],
                    "large": in_large["in_arity"],
                },
                "batch": {"small": in_small["batch"], "large": in_large["batch"]},
                "callers": {
                    "small": in_small["callers"],
                    "large": in_large["callers"],
                },
            }
        )

    rows.sort(key=lambda row: (-row["delta"], row["frame"], row["shape"]))
    return rows


def print_report(name, flow, small_exec, large_exec, rows):
    growing = [row for row in rows if row["delta"] > 0]
    shrinking = [row for row in rows if row["delta"] < 0]
    constant = [row for row in rows if row["delta"] == 0]

    movement = sum(abs(row["delta"]) for row in rows)
    unit = flow.workload_unit

    print(
        f"\n{name}: {small_exec['observed_workload']} -> "
        f"{large_exec['observed_workload']} {unit}"
    )

    # Reconciliation first: a report that does not add up to the number it
    # explains is describing something else.
    for label, execution in (("small", small_exec), ("large", large_exec)):
        gap = unattributed(execution)
        print(
            f"  {label:<5} {execution['total']:>5} queries  "
            f"= {len(execution['events'])} attributed "
            f"+ {gap} outside execute_wrapper"
        )

    shown, covered = [], 0.0
    for row in growing:
        shown.append(row)
        covered += abs(row["delta"])
        if movement and covered / movement >= COVERAGE:
            break

    print(f"\n  Growth drivers ({len(shown)} of {len(growing)} growing groups)")
    _print_rows(shown, unit)

    if shrinking:
        print(f"\n  Groups that shrank ({len(shrinking)})")
        _print_rows(shrinking, unit)

    fixed_shown = min(FIXED_SHOWN, len(constant))
    print(f"\n  Largest fixed cost ({fixed_shown} of {len(constant)} constant groups)")
    _print_rows(
        sorted(constant, key=lambda row: -row["small"])[:FIXED_SHOWN], unit, rate=False
    )

    # Every group that shrank is printed above, so only growing groups the
    # coverage cut left out are unseen. Counting the shrinking ones here as
    # well would tell a reader something is hidden that they have just read.
    hidden = [row for row in growing if row not in shown]
    if hidden:
        net = sum(row["delta"] for row in hidden)
        gross = sum(abs(row["delta"]) for row in hidden)
        print(
            f"\n  {len(hidden)} further changed group(s) not shown: "
            f"net {net:+d}, gross movement {gross}"
        )


def _width(label, spans):
    """One side note per group for the widths its shape hides.

    A collapsed IN list and an executemany both mean one statement doing a
    variable amount of work, which a count alone cannot show.
    """
    small, large = spans["small"], spans["large"]
    if small is None and large is None:
        return ""

    def side(span):
        if span is None:
            return "-"
        return str(span[0]) if span[0] == span[1] else f"{span[0]}-{span[1]}"

    return f"  [{label} {side(small)} -> {side(large)}]"


def _print_rows(rows, unit, rate=True):
    if not rows:
        print("    none")
        return
    for row in rows:
        if rate:
            head = f"    {row['rate']:+6.2f}/{unit}"
        else:
            head = f"    {row['small']:>6} fixed "
        fixed = f"  (fixed {row['fixed']:.0f})" if rate and row["fixed"] else ""
        print(f"{head}  {row['small']:>5} -> {row['large']:<5}  {row['frame']}{fixed}")
        shape_text = row["shape"]
        if len(shape_text) > 96:
            shape_text = shape_text[:96] + "..."
        notes = _width("IN arity", row["in_arity"]) + _width("batch", row["batch"])
        print(f"{'':>13}{shape_text}{notes}")


# ---------------------------------------------------------------------------
# Parent: temporary database, child processes
# ---------------------------------------------------------------------------


def _child(arguments, database, token, events):
    environment = dict(
        os.environ,
        **{
            run.DB_ENV_VAR: database,
            run.TOKEN_ENV_VAR: token,
            EVENTS_ENV_VAR: events,
        },
    )
    # This interpreter running this file: no shell, and nothing in the command
    # comes from anywhere but the runner itself.
    return subprocess.run(  # noqa: S603
        [sys.executable, os.path.abspath(__file__), *arguments],
        env=environment,
        check=False,
    )


def attribute(name, size, template, directory, index, token):
    """Copy the template and instrument one execution in a fresh child."""
    database = os.path.join(directory, f"attribution-{index:02d}.sqlite3")
    events = os.path.join(directory, f"events-{index:02d}.json")
    shutil.copy(template, database)

    result = _child([CHILD_FLAG, name, "--size", size], database, token, events)
    if result.returncode != 0:
        return None

    with open(events, encoding="utf-8") as handle:
        return json.load(handle)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Attribute a wagtail-localize benchmark flow's query count to the "
            "code that produced it. Diagnostic output only: use "
            "benchmarks/run.py for numbers."
        ),
    )
    parser.add_argument("flow", nargs="?", help="flow name; omit with --list")
    parser.add_argument("--size", help=argparse.SUPPRESS)
    parser.add_argument("--json", help="write the full grouping to this path")
    parser.add_argument("--list", action="store_true", help="print the catalog")
    parser.add_argument(CHILD_FLAG, action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()

    if arguments.attribute_in_child:
        attribute_in_child(arguments.flow, arguments.size)
        return 0

    if arguments.list:
        run.print_catalog()
        return 0

    if not arguments.flow:
        parser.error("give a flow name, or use --list")

    # Resolved from the catalog rather than through run._select, which resolves
    # one execution and therefore wants a size: this command's unit is the flow.
    from benchmarks import catalog as catalog_module

    if arguments.flow not in catalog_module.BY_NAME:
        parser.error(
            f"unknown flow {arguments.flow!r}. "
            f"Known: {', '.join(sorted(catalog_module.BY_NAME))}"
        )
    flow = catalog_module.BY_NAME[arguments.flow]

    # Two sizes are the whole method: with one there is nothing to compare, and
    # a group's count on its own says nothing about whether it scales.
    if len(flow.scale_points) != 2:
        raise SystemExit(
            f"{flow.name} declares {len(flow.scale_points)} scale point(s). "
            f"Attribution compares two, because what it reports is the "
            f"difference between them."
        )

    directory = tempfile.mkdtemp(prefix="wl-attribution-")
    try:
        token = run._own_directory(directory)
        template = run._build_template(directory, token)
        executions = []
        for index, point in enumerate(flow.scale_points):
            execution = attribute(
                flow.name, point.label, template, directory, index, token
            )
            if execution is None:
                print(f"{flow.name} [{point.label}]  FAILED", file=sys.stderr)
                return 1
            executions.append(execution)
    finally:
        shutil.rmtree(directory)

    small_exec, large_exec = executions
    rows = build(small_exec, large_exec)
    print_report(flow.name, flow, small_exec, large_exec, rows)

    if arguments.json:
        with open(arguments.json, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "flow": flow.name,
                    "sizes": {
                        point.label: {
                            "observed_workload": execution["observed_workload"],
                            "total": execution["total"],
                            "attributed": len(execution["events"]),
                            "unattributed": unattributed(execution),
                        }
                        for point, execution in zip(
                            flow.scale_points, executions, strict=True
                        )
                    },
                    "groups": rows,
                },
                handle,
                indent=2,
            )
        print(f"\nwrote {arguments.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
