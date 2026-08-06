"""Diagnose one catalog flow with Django Query Doctor.

    python benchmarks/run_query_doctor.py --list
    python benchmarks/run_query_doctor.py core_page_index --size small
    python benchmarks/run_query_doctor.py all

run.py says how much work a flow does. It does not say why, and it must not
learn: a measurement taken under instrumentation is a measurement of the
instrumentation too. This runner answers the second question separately —
same catalog, same fixture, same isolation, but the flow runs inside Query
Doctor instead of inside a stopwatch, and what it prints is a diagnosis rather
than a number anyone should record.

Nothing here is a baseline. Query Doctor wraps every cursor, walks the stack
for each query, and analyses the lot afterwards; the query count it reports is
real, but its timings carry that overhead. Compare numbers with run.py and
explanations with this.

The structure of an execution is deliberately identical to run.py's: a parent
that never imports Django, a template database built by a child, and one fresh
child per execution against its own copy. That is what makes the two commands
comparable, and it is reused from run.py rather than restated here, so the two
cannot drift apart. The dependency only points this way: run.py knows nothing
about this file or about Query Doctor.
"""

import argparse
import importlib.util
import os
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


CHILD_FLAG = "--diagnose-in-child"

# Said the same way wherever it is discovered: by the parent before it builds
# anything, and by the child if the two ever run in different environments.
MISSING_QUERY_DOCTOR = (
    "django-query-doctor is not installed in this environment.\n"
    "It is a diagnostic dependency, deliberately kept out of the project's "
    "requirements and out of benchmarks/run.py, so the benchmark harness runs "
    "without it.\n"
    "Use the optional diagnostic environment described in benchmarks/README.md, "
    "or install django-query-doctor into the environment you are running from."
)

# Worst first, so a long report opens with the finding worth reading. Keyed by
# value rather than by enum member: a version that adds a severity should sort
# it last, not fail.
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


# ---------------------------------------------------------------------------
# Query Doctor, imported only where it is used
# ---------------------------------------------------------------------------


def _query_doctor_installed():
    """Whether Query Doctor could be imported, without importing it.

    The parent runs this. find_spec locates the module and stops, so the parent
    keeps its one important property: it initialises nothing.
    """
    return importlib.util.find_spec("query_doctor") is not None


def _diagnose_queries():
    """Query Doctor's context manager, imported at the point of use.

    Deferred so that --list, an invalid selection, and importing this module
    all cost nothing and work in an environment without the tool.
    """
    try:
        from query_doctor import diagnose_queries
    except ImportError as error:
        raise SystemExit(f"{MISSING_QUERY_DOCTOR}\n({error})") from error
    return diagnose_queries


# ---------------------------------------------------------------------------
# Child: the only side that touches Django
# ---------------------------------------------------------------------------


def _prescription_lines(prescription):
    """One diagnosed issue, as the lines that describe it."""
    severity = prescription.severity.value.upper()
    issue = prescription.issue_type.value
    count = prescription.query_count

    header = f"  {severity}  {issue}"
    if count:
        header += f"  ({count} queries)"

    lines = [header, f"    {prescription.description}"]
    if prescription.fix_suggestion:
        lines.append(f"    fix: {prescription.fix_suggestion}")

    callsite = prescription.callsite
    if callsite is not None:
        lines.append(
            f"    at {callsite.filepath}:{callsite.line_number} "
            f"in {callsite.function_name}"
        )
    return lines


def print_report(name, size, flow, observed, report):
    """The diagnosis, under the execution it belongs to.

    A report that did not name its flow, size and observed workload would be a
    page of prescriptions nobody can place: the same flow diagnoses differently
    at each scale point, which is usually the whole point of running it.
    """
    workload = "—"
    if flow.workload_unit:
        workload = f"{observed} {flow.workload_unit}"

    print(f"\n{name} [{size or '-'}]  {workload}")
    print(
        f"  {report.total_queries} queries, "
        f"{report.total_time_ms:.1f} ms of database time under diagnosis"
    )

    if not report.prescriptions:
        print("  no prescriptions")
        return

    prescriptions = sorted(
        report.prescriptions,
        key=lambda p: (
            _SEVERITY_ORDER.get(p.severity.value, len(_SEVERITY_ORDER)),
            -p.query_count,
        ),
    )
    print(f"  {len(prescriptions)} prescription(s)")
    for prescription in prescriptions:
        print()
        for line in _prescription_lines(prescription):
            print(line)


def diagnose_in_child(name, size):
    """Prepare the fixture, diagnose one execution, verify it, report.

    The diagnosed region is exactly the flow's own call, for the same reason
    run.py measures exactly that call: fixture construction and setup are
    scaffolding, and their queries would drown the ones being explained.
    Verification runs after the diagnosis has closed, so what it queries is not
    attributed to the flow.
    """
    # Both before Django exists, and both borrowed from run.py so the two
    # commands cannot disagree about what a valid selection is.
    run.guard_database()
    catalog, flow, point = run._select(name, size)

    from benchmarks.env import bootstrap

    bootstrap()

    diagnose_queries = _diagnose_queries()

    ctx = catalog.prepare()
    if flow.setup:
        flow.setup(ctx, size)

    with diagnose_queries() as report:
        artifacts = flow.run(ctx, size)

    observed = flow.verify(ctx, size, artifacts)

    # The same rule the harness applies: a diagnosis of a scenario that did not
    # build is an explanation of something else.
    if point is not None and observed != point.expected_workload:
        raise SystemExit(
            f"{name} [{size}] produced {observed} {flow.workload_unit}, but "
            f"the scale point declares {point.expected_workload}. The fixture "
            f"is not building the scenario this size is supposed to diagnose."
        )

    print_report(name, size, flow, observed, report)


# ---------------------------------------------------------------------------
# Parent: temporary database, child processes
# ---------------------------------------------------------------------------


def _child(arguments, database, token):
    """Run this file again as a child, pointed at `database`.

    Output is inherited rather than captured: the report is for a person
    reading the terminal, and there is no machine-readable channel to keep
    clean.
    """
    environment = dict(
        os.environ, **{run.DB_ENV_VAR: database, run.TOKEN_ENV_VAR: token}
    )
    # This interpreter running this file: no shell, and nothing in the command
    # comes from anywhere but the runner itself.
    return subprocess.run(  # noqa: S603
        [sys.executable, os.path.abspath(__file__), *arguments],
        env=environment,
        check=False,
    )


def diagnose(name, size, template, directory, index, token):
    """Copy the template and diagnose one execution in a fresh child."""
    database = os.path.join(directory, f"diagnose-{index:02d}.sqlite3")
    shutil.copy(template, database)

    arguments = [CHILD_FLAG, name]
    if size is not None:
        arguments += ["--size", size]
    result = _child(arguments, database, token)

    if result.returncode != 0:
        # The child was not captured, so whatever it said is already on this
        # terminal. This only marks which execution it belonged to.
        print(f"{name} [{size or '-'}]  FAILED", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Explain a wagtail-localize benchmark flow with Django Query "
            "Doctor. Diagnostic output only: use benchmarks/run.py for numbers."
        ),
    )
    parser.add_argument(
        "flow", nargs="?", help=f"flow name or {run.ALL}; omit with --list"
    )
    parser.add_argument("--size", help="diagnose only this scale point")
    parser.add_argument("--list", action="store_true", help="print the catalog")
    parser.add_argument(CHILD_FLAG, action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()

    if arguments.diagnose_in_child:
        diagnose_in_child(arguments.flow, arguments.size)
        return 0

    if arguments.list:
        # The catalog is run.py's to describe, and printing it needs neither
        # Django nor Query Doctor.
        run.print_catalog()
        return 0

    if not arguments.flow:
        parser.error(f"give a flow name or {run.ALL}, or use --list")

    # Resolved before anything is created, so an impossible selection costs no
    # temporary directory and no migration.
    try:
        plan = run._executions_for(arguments.flow, arguments.size)
    except ValueError as error:
        parser.error(str(error))

    # Checked here rather than in the child: a missing tool should cost a
    # message, not a migrated database and one failing process per execution.
    if not _query_doctor_installed():
        raise SystemExit(MISSING_QUERY_DOCTOR)

    print(
        "Query Doctor instruments every cursor, so these timings are not "
        "comparable with benchmarks/run.py.",
        file=sys.stderr,
    )

    directory = tempfile.mkdtemp(prefix="wl-query-doctor-")
    ok = True
    try:
        token = run._own_directory(directory)
        template = run._build_template(directory, token)
        for index, (flow, size) in enumerate(plan):
            ok &= diagnose(flow.name, size, template, directory, index, token)
    finally:
        shutil.rmtree(directory)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
