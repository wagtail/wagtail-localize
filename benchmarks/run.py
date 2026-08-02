"""Run the benchmark catalog.

    python benchmarks/run.py --list
    python benchmarks/run.py edit_translation_get
    python benchmarks/run.py edit_translation_get --size small
    python benchmarks/run.py all

Every execution runs in its own child process against its own fresh copy of an
empty migrated database. That is what makes two executions comparable: copying
a file gives an identical starting state without deleting anything, and a new
process leaves no warm caches behind — neither Django's, nor Wagtail's, nor
Python's import cache.

The parent never imports Django. It creates a temporary directory, has a child
build the template database, then for each execution copies the template and
launches a child. Because the parent holds no connection, there is nothing to
close before copying, and no file outside its own temporary directory is
modified. The children are launched with sys.executable, so the harness runs in
whatever environment invoked it.

The child prints one JSON line for the parent to read. That is an internal
channel, not the reporting format: the console output below is built by the
parent, and a machine-readable output mode is a separate concern.
"""

import argparse
import datetime
import importlib.metadata
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile


if __name__ == "__main__":
    # Running this file directly puts benchmarks/ on sys.path, not the repo
    # root, so `benchmarks.*` would not resolve. Imported as a package the root
    # is already reachable, and inserting it would change sys.path for whoever
    # imported us. The single identity matters: loaded flat and as a package,
    # `catalog` and `benchmarks.catalog` are two objects with separate state.
    _REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)


# The env var env.bootstrap() reads. Named here so the parent, which must not
# import anything Django-adjacent, does not have to import env to set it.
DB_ENV_VAR = "WL_BENCHMARK_DB"
# Not a secret: a per-invocation marker that says "this harness made this
# directory". It guards against accident, not against anyone hostile.
TOKEN_ENV_VAR = "WL_BENCHMARK_TOKEN"  # noqa: S105
TOKEN_FILENAME = ".wl-benchmark-token"  # noqa: S105

CHILD_FLAG = "--execute-in-child"

# Reserved: it selects the whole catalog, so no flow may be called this.
ALL = "all"

# The child writes its result on one line with this prefix, so the parent reads
# a line it can identify rather than guessing from the shape of the output.
RESULT_PREFIX = "WL_BENCHMARK_RESULT="

# Bump when the shape of the --json file changes, so a reader can tell whether
# it understands a file before trusting it.
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Child: the only side that touches Django
# ---------------------------------------------------------------------------


def guard_database():
    """Validate that the database belongs to this harness invocation.

    The token prevents accidentally running an internal child command against
    another database. It is a safety guard, not a security boundary.

    Returns the resolved path, or exits non-zero without opening the database.
    """
    database = os.environ.get(DB_ENV_VAR)
    token = os.environ.get(TOKEN_ENV_VAR)

    if not database:
        raise SystemExit(f"{DB_ENV_VAR} is not set; start from run.py.")
    if not token:
        raise SystemExit(
            f"{TOKEN_ENV_VAR} is not set. The child modes are internal: the "
            f"parent passes a token so the harness cannot be pointed at a "
            f"database it does not own. Start from run.py."
        )

    resolved = os.path.realpath(database)
    directory = os.path.dirname(resolved)
    token_file = os.path.join(directory, TOKEN_FILENAME)

    if not os.path.isfile(token_file):
        raise SystemExit(
            f"refusing to use {resolved}: it is not inside a directory this "
            f"harness created, so it may be a database you care about. "
            f"The database was not opened or modified."
        )

    with open(token_file) as handle:
        if handle.read().strip() != token:
            raise SystemExit(
                f"refusing to use {resolved}: the token does not match the one "
                f"in {TOKEN_FILENAME}. The database was not opened or "
                f"modified."
            )

    return resolved


def _select(name, size):
    """Validate and resolve a catalog selection before building the fixture."""
    from benchmarks import catalog

    if name not in catalog.BY_NAME:
        raise SystemExit(
            f"unknown flow {name!r}. Known: {', '.join(sorted(catalog.BY_NAME))}"
        )

    flow = catalog.BY_NAME[name]
    declared = flow.sizes()

    if flow.scale_points and size is None:
        raise SystemExit(
            f"{flow.name} declares scale points, so it needs a size. "
            f"Declared: {', '.join(p.label for p in flow.scale_points)}"
        )
    if not flow.scale_points and size is not None:
        raise SystemExit(
            f"{flow.name} declares no scale points, so it takes no size; got {size!r}."
        )
    if size not in declared:
        raise SystemExit(
            f"{flow.name} has no size {size!r}. "
            f"Declared: {', '.join(str(s) for s in declared)}"
        )

    return catalog, flow, flow.scale_point(size)


def run_in_child(name, size):
    """Prepare the fixture, measure one execution, verify it, report.

    The measured region is exactly the flow's own call. Fixture construction
    and the flow's setup happen before it; verification happens after the
    context manager has closed, so neither lands in the numbers.
    """
    # Both run before Django exists: an invalid database must not be opened,
    # and an invalid selection must not cost a fixture build.
    guard_database()
    catalog, flow, point = _select(name, size)

    from benchmarks.env import bootstrap

    bootstrap()

    from time import perf_counter

    from django.db import connection, reset_queries
    from django.test.utils import CaptureQueriesContext

    ctx = catalog.prepare()
    if flow.setup:
        flow.setup(ctx, size)

    # CaptureQueriesContext enables its own debug cursor, so DEBUG remains off
    # and the code under measurement runs under the benchmark's own settings.
    # Under those settings the fixture does not fill connection.queries_log;
    # this clears it in case setup or optional instrumentation turned query
    # logging on, because the log is a deque(maxlen=9000) and a full one makes
    # the captured positions coincide and report zero with only a UserWarning.
    reset_queries()

    with CaptureQueriesContext(connection) as captured:
        started = perf_counter()
        artifacts = flow.run(ctx, size)
        seconds = perf_counter() - started

    observed = flow.verify(ctx, size, artifacts)

    # Comparing here rather than inside each verify() means no flow can forget
    # to check the cardinality it declared. A mismatch means the numbers
    # describe a different workload than the one named.
    if point is not None and observed != point.expected_workload:
        raise SystemExit(
            f"{name} [{size}] produced {observed} {flow.workload_unit}, but "
            f"the scale point declares {point.expected_workload}. The fixture "
            f"is not building the scenario this size is supposed to measure."
        )

    print(
        RESULT_PREFIX
        + json.dumps(
            {
                "pid": os.getpid(),
                "database": os.environ[DB_ENV_VAR],
                "queries": len(captured),
                "seconds": seconds,
                "observed_workload": observed,
                "expected_workload": point.expected_workload if point else None,
                "workload_unit": flow.workload_unit,
            }
        )
    )


# ---------------------------------------------------------------------------
# Parent: temporary database, child processes, results
# ---------------------------------------------------------------------------


def _own_directory(directory):
    """Mark `directory` as belonging to this invocation, and return its token."""
    token = secrets.token_hex(16)
    with open(os.path.join(directory, TOKEN_FILENAME), "w") as handle:
        handle.write(token)
    return token


def _child(args, database, token):
    """Run this file again as a child, pointed at `database`."""
    environment = dict(os.environ, **{DB_ENV_VAR: database, TOKEN_ENV_VAR: token})
    # The command is this interpreter running this file: no shell, and no part
    # of it comes from anywhere but the harness itself.
    return subprocess.run(  # noqa: S603
        [sys.executable, os.path.abspath(__file__), *args],
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _build_template(directory, token):
    """Have a child create the migrated, empty database every execution copies.

    Done in a child because the parent must not initialise Django: an
    initialised parent would hold a connection to the template, and a file with
    an open connection is not safe to copy.
    """
    template = os.path.join(directory, "template.sqlite3")
    result = _child(["--build-template"], template, token)
    if result.returncode != 0:
        raise SystemExit(f"could not create the template database:\n{result.stderr}")
    return template


def build_template_in_child():
    guard_database()

    from benchmarks.env import bootstrap

    bootstrap()

    from django.core.management import call_command

    call_command("migrate", verbosity=0)
    # A Locale post_save receiver in Wagtail clears a cached value, so without
    # this table the fixture dies on its first locale.
    call_command("createcachetable", verbosity=0)


def execute(name, size, template, directory, index, token):
    """Copy the template and run one execution in a fresh child."""
    database = os.path.join(directory, f"run-{index:02d}.sqlite3")
    shutil.copy(template, database)

    arguments = [CHILD_FLAG, name]
    if size is not None:
        arguments += ["--size", size]
    result = _child(arguments, database, token)

    if result.returncode != 0:
        return {"process": name, "size": size, "error": result.stderr.strip()}

    lines = [
        line[len(RESULT_PREFIX) :]
        for line in result.stdout.splitlines()
        if line.startswith(RESULT_PREFIX)
    ]
    if not lines:
        return {
            "process": name,
            "size": size,
            "error": (
                f"the child produced no {RESULT_PREFIX} line:\n{result.stdout.strip()}"
            ),
        }

    # A child that printed something unusable is this execution's failure, not
    # the whole run's: `all` has to reach the executions after it.
    try:
        payload = json.loads(lines[-1])
        return {
            "process": name,
            "size": size,
            "queries": payload["queries"],
            "seconds": payload["seconds"],
            "workload_unit": payload["workload_unit"],
            "expected_workload": payload["expected_workload"],
            "observed_workload": payload["observed_workload"],
            "pid": payload["pid"],
            "database": payload["database"],
        }
    except (ValueError, TypeError, KeyError) as error:
        return {
            "process": name,
            "size": size,
            "error": f"unusable {RESULT_PREFIX} line: {error}\n{lines[-1]}",
        }


def _git(*arguments):
    """A short git query.

    Raises RuntimeError when git cannot answer: a document that says which
    commit was measured is the point, and a null there would be a run nobody
    can place.
    """
    # Partial path on purpose: the harness records whichever git the developer
    # is already using, and a wrong answer only affects provenance, never a
    # measurement.
    try:
        result = subprocess.run(  # noqa: S603
            ["git", *arguments],  # noqa: S607
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeError(f"cannot run git: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or f"exit status {result.returncode}"
        raise RuntimeError(f"git {' '.join(arguments)}: {detail}")
    return result.stdout.strip()


# Public key in the document, and the distribution name the environment
# records it under. The parent reads metadata rather than importing these, so
# it still never initialises Django.
MEASURED_PACKAGES = {
    "django": "Django",
    "wagtail": "wagtail",
    "wagtail_localize": "wagtail-localize",
}


def _versions():
    """The versions of the packages under measurement.

    Raises LookupError naming what is missing: provenance that cannot say what
    was measured is worse than no file at all.
    """
    versions = {"python": platform.python_version()}
    missing = []
    for key, distribution in MEASURED_PACKAGES.items():
        try:
            versions[key] = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            missing.append(distribution)
    if missing:
        raise LookupError(
            f"no installed metadata for {', '.join(missing)}, so the run cannot "
            f"record what it measured"
        )
    return versions


def _check_json_path(path):
    """Raise ValueError unless the run could write its results to `path`."""
    if os.path.isdir(path):
        raise ValueError(f"{path} is a directory")

    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        raise ValueError(f"no directory {parent}")
    if not os.access(parent, os.W_OK):
        raise ValueError(f"{parent} is not writable")
    if os.path.exists(path) and not os.access(path, os.W_OK):
        raise ValueError(f"{path} is not writable")


def _provenance(selection):
    """What a reader needs to know before trusting the numbers."""
    dirty = _git("status", "--porcelain")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "commit": _git("rev-parse", "HEAD"),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        # Whatever git status reports for this checkout, under the ignore
        # rules in force there: anything ignored is invisible here.
        "working_tree_clean": dirty == "",
        "versions": _versions(),
        "selection": selection,
    }


def _public_result(result):
    """One execution, reduced to what belongs in a shared file.

    The database path and the child's pid are private to a run, and timings
    from a single execution are not a signal this format publishes.
    """
    if "error" in result:
        return {
            "flow": result["process"],
            "size": result["size"],
            "status": "failed",
            "queries": None,
            "workload_unit": None,
            "expected_workload": None,
            "observed_workload": None,
        }
    return {
        "flow": result["process"],
        "size": result["size"],
        "status": "ok",
        "queries": result["queries"],
        "workload_unit": result["workload_unit"],
        "expected_workload": result["expected_workload"],
        "observed_workload": result["observed_workload"],
    }


def _write_json(path, provenance, results):
    """Write the run to `path`.

    A run with a failed execution is written, but marked incomplete: it is a
    record of what happened, never a baseline to compare against.
    """
    executions = [_public_result(result) for result in results]
    document = {
        **provenance,
        "status": (
            "complete" if all(e["status"] == "ok" for e in executions) else "incomplete"
        ),
        "executions": executions,
    }
    with open(path, "w") as handle:
        json.dump(document, handle, indent=2, sort_keys=False)
        handle.write("\n")


def _executions_for(name, size):
    """The (flow, size) pairs a command line selects, in catalog order.

    Raises ValueError with the message the CLI should show. Kept apart from
    main() so a selection can be checked without creating a database or a
    process.
    """
    from benchmarks import catalog

    if name == ALL:
        if size is not None:
            raise ValueError(f"--size cannot be used with {ALL}")
        return list(catalog.executions())

    if name not in catalog.BY_NAME:
        raise ValueError(
            f"unknown flow {name!r}. "
            f"Known: {', '.join(sorted(catalog.BY_NAME))}, or {ALL}"
        )

    flow = catalog.BY_NAME[name]
    if size is None:
        return [(flow, declared) for declared in flow.sizes()]
    if not flow.scale_points:
        raise ValueError(f"{flow.name} takes no size")
    if size not in flow.sizes():
        raise ValueError(
            f"{flow.name} has no size {size!r}. "
            f"Declared: {', '.join(str(s) for s in flow.sizes())}"
        )
    return [(flow, size)]


def print_catalog():
    from benchmarks import catalog

    flows = catalog.CATALOG
    print(f"{len(flows)} process(es), {len(catalog.executions())} execution(s)\n")
    for flow in flows:
        sizes = ", ".join(point.label for point in flow.scale_points) or "—"
        print(f"{flow.name}")
        print(f"    group      {flow.group}")
        print(f"    sizes      {sizes}")
        if flow.workload_unit:
            print(f"    workload   {flow.workload_unit}")
            for point in flow.scale_points:
                print(f"      {point.label:8}expects {point.expected_workload}")
        print(f"    entrypoint {flow.entrypoint}")
        print(f"    why        {flow.why}")
        print()


def report(result):
    if "error" in result:
        print(f"{result['process']} [{result['size'] or '-'}]  FAILED", file=sys.stderr)
        print(result["error"], file=sys.stderr)
        return False

    size = result["size"] or "-"
    line = (
        f"{result['process']} [{size}]  "
        f"{result['queries']} queries  {result['seconds'] * 1000:.1f} ms"
    )
    if result["workload_unit"]:
        line += (
            f"  {result['observed_workload']} {result['workload_unit']}"
            f" (expected {result['expected_workload']})"
        )
    print(line)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Measure wagtail-localize flows.",
    )
    parser.add_argument("flow", nargs="?", help=f"flow name or {ALL}; omit with --list")
    parser.add_argument("--size", help="run only this scale point")
    parser.add_argument("--list", action="store_true", help="print the catalog")
    parser.add_argument(
        "--json", dest="json_path", metavar="PATH", help="also write the run to PATH"
    )
    parser.add_argument(CHILD_FLAG, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--build-template", action="store_true", help=argparse.SUPPRESS)
    arguments = parser.parse_args()

    if arguments.build_template:
        build_template_in_child()
        return 0

    if arguments.execute_in_child:
        run_in_child(arguments.flow, arguments.size)
        return 0

    if arguments.list:
        if arguments.json_path:
            parser.error("--json has nothing to write with --list")
        print_catalog()
        return 0

    if not arguments.flow:
        parser.error(f"give a flow name or {ALL}, or use --list")

    # Resolved before anything is created, so an impossible selection costs no
    # temporary directory and no migration.
    try:
        plan = _executions_for(arguments.flow, arguments.size)
    except ValueError as error:
        parser.error(str(error))

    # Everything about --json is settled before anything runs: a path that
    # cannot be written should cost a message, not a run whose results are then
    # thrown away.
    provenance = None
    if arguments.json_path:
        try:
            _check_json_path(arguments.json_path)
            provenance = _provenance({"flow": arguments.flow, "size": arguments.size})
        except (ValueError, LookupError, RuntimeError) as error:
            parser.error(f"--json: {error}")

    directory = tempfile.mkdtemp(prefix="wl-benchmark-")
    ok = True
    results = []
    try:
        token = _own_directory(directory)
        # One template per invocation; every execution copies it. The index is
        # unique across the whole run, so no two executions share a database.
        template = _build_template(directory, token)
        for index, (flow, size) in enumerate(plan):
            result = execute(flow.name, size, template, directory, index, token)
            results.append(result)
            ok &= report(result)
    finally:
        shutil.rmtree(directory)

    # Written from the results the run already produced: nothing is executed
    # twice and the measured region is untouched.
    if arguments.json_path:
        _write_json(arguments.json_path, provenance, results)
        print(f"wrote {arguments.json_path}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
