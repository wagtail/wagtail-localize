"""Structural tests for the Query Doctor runner.

The runner is a manual diagnostic tool, so these tests do not diagnose
anything: they check the properties that keep it separate from the benchmark
harness — that it needs no Query Doctor to list or to refuse a selection, that
it diagnoses the flow's own call and nothing around it, and that run.py is not
dragged along with it.

They run in an environment that may or may not have django-query-doctor
installed, so nothing here may depend on either.
"""

import ast
import builtins
import contextlib
import importlib.util
import io
import os
import sys

from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from benchmarks import catalog, run, run_query_doctor


BENCHMARKS = os.path.dirname(os.path.abspath(run.__file__))

DJANGO = ("django", "wagtail")
QUERY_DOCTOR = ("query_doctor",)
BOOTSTRAP = (*DJANGO, "benchmarks.env", "benchmarks.settings")


def _source_of(filename):
    with open(os.path.join(BENCHMARKS, filename)) as handle:
        return handle.read()


def _imported_names(node):
    """Every module path an import node names, or () if it is not an import."""
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return (module, *(f"{module}.{alias.name}" for alias in node.names))
    return ()


@contextlib.contextmanager
def query_doctor_missing():
    """Make importing Query Doctor fail, whatever this environment has.

    The runner has to behave the same for someone who never installed the tool,
    and the test suite must not need it either.
    """
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "query_doctor" or name.startswith("query_doctor."):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, *args, **kwargs):
        if name == "query_doctor":
            return None
        return real_find_spec(name, *args, **kwargs)

    with (
        mock.patch.object(builtins, "__import__", side_effect=fake_import),
        mock.patch.object(importlib.util, "find_spec", side_effect=fake_find_spec),
    ):
        yield


def _flow(**overrides):
    """A catalog Flow whose callables are whatever a test needs."""
    fields = {
        "name": "fake_flow",
        "group": "fake",
        "why": "w",
        "entrypoint": "e",
        "covers": (),
        "run": lambda ctx, size: None,
        "verify": lambda ctx, size, artifacts: None,
    }
    fields.update(overrides)
    return catalog.Flow(**fields)


def _report(**overrides):
    """Enough of a DiagnosisReport for the runner to print."""
    fields = {"total_queries": 3, "total_time_ms": 1.5, "prescriptions": []}
    fields.update(overrides)
    return SimpleNamespace(**fields)


@contextlib.contextmanager
def _child_environment(flow, events, report=None, prepared="ctx"):
    """Everything the child touches, replaced by something that records.

    No database, no Django bootstrap and no Query Doctor: what is under test is
    the order of the calls and where the diagnosis begins and ends.
    """

    @contextlib.contextmanager
    def fake_diagnose_queries():
        events.append("diagnose:enter")
        yield report if report is not None else _report()
        events.append("diagnose:exit")

    def fake_prepare():
        events.append("prepare")
        return prepared

    with (
        mock.patch.object(run, "guard_database", return_value="db"),
        mock.patch.dict(catalog.BY_NAME, {flow.name: flow}),
        mock.patch.object(catalog, "prepare", side_effect=fake_prepare),
        mock.patch("benchmarks.env.bootstrap"),
        mock.patch.object(
            run_query_doctor, "_diagnose_queries", return_value=fake_diagnose_queries
        ),
    ):
        yield


@contextlib.contextmanager
def _captured_stdout():
    stream = io.StringIO()
    with mock.patch.object(sys, "stdout", stream):
        yield stream


class TestListingNeedsNothing(SimpleTestCase):
    """--list is a catalog listing. It has to work in an environment with no
    Query Doctor and no database, exactly like run.py --list."""

    def test_the_module_imports_no_query_doctor_and_no_django_at_module_level(self):
        for node in ast.parse(_source_of("run_query_doctor.py")).body:
            for name in _imported_names(node):
                self.assertFalse(
                    name.startswith(DJANGO + QUERY_DOCTOR),
                    f"run_query_doctor.py imports {name} at module level",
                )

    def test_the_parent_code_path_defers_every_django_import(self):
        source = ast.parse(_source_of("run_query_doctor.py"))
        child_side = {"diagnose_in_child"}

        for node in source.body:
            if not isinstance(node, ast.FunctionDef) or node.name in child_side:
                continue
            for inner in ast.walk(node):
                for name in _imported_names(inner):
                    self.assertFalse(
                        name.startswith(BOOTSTRAP),
                        f"parent function {node.name}() imports {name}",
                    )

    def test_listing_works_without_query_doctor(self):
        with (
            query_doctor_missing(),
            mock.patch.object(sys, "argv", ["run_query_doctor.py", "--list"]),
            _captured_stdout() as stdout,
        ):
            code = run_query_doctor.main()

        self.assertEqual(code, 0)
        self.assertIn("edit_translation_get", stdout.getvalue())

    def test_listing_does_not_look_for_query_doctor_at_all(self):
        with (
            mock.patch.object(run_query_doctor, "_query_doctor_installed") as installed,
            mock.patch.object(run_query_doctor, "_diagnose_queries") as diagnose,
            mock.patch.object(sys, "argv", ["run_query_doctor.py", "--list"]),
            _captured_stdout(),
        ):
            run_query_doctor.main()

        installed.assert_not_called()
        diagnose.assert_not_called()


class TestSelectionIsRefusedEarly(SimpleTestCase):
    """An impossible selection is worth a message, not a migrated database."""

    def _main(self, argv):
        stderr = io.StringIO()
        with (
            mock.patch.object(run, "_build_template") as build_template,
            mock.patch.object(run_query_doctor, "diagnose") as diagnose,
            mock.patch.object(sys, "argv", ["run_query_doctor.py", *argv]),
            mock.patch.object(sys, "stderr", stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            run_query_doctor.main()
        return str(raised.exception), stderr.getvalue(), build_template, diagnose

    def test_an_unknown_flow_names_the_known_ones(self):
        _code, message, build_template, diagnose = self._main(["no_such_flow"])
        self.assertIn("unknown flow", message)
        self.assertIn("edit_translation_get", message)
        build_template.assert_not_called()
        diagnose.assert_not_called()

    def test_an_undeclared_size_is_refused(self):
        _code, message, build_template, _ = self._main(
            ["edit_translation_get", "--size", "enormous"]
        )
        self.assertIn("no size 'enormous'", message)
        self.assertIn("small, large", message)
        build_template.assert_not_called()

    def test_a_size_on_a_flow_without_scale_points_is_refused(self):
        _code, message, build_template, _ = self._main(
            ["submit_snippet_post", "--size", "small"]
        )
        self.assertIn("takes no size", message)
        build_template.assert_not_called()

    def test_no_flow_and_no_list_is_refused(self):
        _code, message, build_template, _ = self._main([])
        self.assertIn("give a flow name", message)
        build_template.assert_not_called()

    def test_all_selects_the_whole_catalog(self):
        """The plan for `all` is run.py's, so the two commands cover the same
        executions in the same order."""
        selected = []

        def fake_diagnose(name, size, template, directory, index, token):
            selected.append((name, size))
            return True

        with (
            mock.patch.object(run, "_build_template", return_value="template"),
            mock.patch.object(
                run_query_doctor, "_query_doctor_installed", return_value=True
            ),
            mock.patch.object(run_query_doctor, "diagnose", side_effect=fake_diagnose),
            mock.patch.object(sys, "argv", ["run_query_doctor.py", run.ALL]),
            mock.patch.object(sys, "stderr", io.StringIO()),
            _captured_stdout(),
        ):
            code = run_query_doctor.main()

        self.assertEqual(code, 0)
        self.assertEqual(
            selected, [(flow.name, size) for flow, size in catalog.executions()]
        )


class TestMissingQueryDoctorSaysSo(SimpleTestCase):
    def test_the_parent_stops_before_building_anything(self):
        with (
            query_doctor_missing(),
            mock.patch.object(run, "_build_template") as build_template,
            mock.patch.object(sys, "argv", ["run_query_doctor.py", run.ALL]),
            self.assertRaises(SystemExit) as raised,
        ):
            run_query_doctor.main()

        message = str(raised.exception)
        self.assertIn("django-query-doctor is not installed", message)
        self.assertIn("benchmarks/README.md", message)
        build_template.assert_not_called()

    def test_the_child_says_the_same_thing(self):
        with query_doctor_missing(), self.assertRaises(SystemExit) as raised:
            run_query_doctor._diagnose_queries()

        self.assertIn("django-query-doctor is not installed", str(raised.exception))


class TestTheDiagnosedRegion(SimpleTestCase):
    """Fixture, setup and verification are scaffolding: their queries would be
    attributed to the flow if they ran inside the diagnosis."""

    @staticmethod
    def _recorder(events, label):
        """A flow callable that only says it was called."""

        def call(*args):
            events.append(label)

        return call

    def test_prepare_setup_run_and_verify_happen_in_that_order(self):
        events = []
        flow = _flow(
            setup=self._recorder(events, "setup"),
            run=self._recorder(events, "run"),
            verify=self._recorder(events, "verify"),
        )

        with _child_environment(flow, events), _captured_stdout():
            run_query_doctor.diagnose_in_child(flow.name, None)

        self.assertEqual(
            events,
            ["prepare", "setup", "diagnose:enter", "run", "diagnose:exit", "verify"],
        )

    def test_a_flow_without_setup_is_diagnosed_the_same_way(self):
        events = []
        flow = _flow(
            run=self._recorder(events, "run"), verify=self._recorder(events, "verify")
        )

        with _child_environment(flow, events), _captured_stdout():
            run_query_doctor.diagnose_in_child(flow.name, None)

        self.assertEqual(
            events, ["prepare", "diagnose:enter", "run", "diagnose:exit", "verify"]
        )

    def test_the_flow_receives_the_prepared_fixture_and_the_size(self):
        seen = {}

        def setup(ctx, size):
            seen["setup"] = (ctx, size)

        def run_flow(ctx, size):
            seen["run"] = (ctx, size)
            return "artifacts"

        def verify(ctx, size, artifacts):
            seen["verify"] = (ctx, size, artifacts)
            return 1

        flow = _flow(
            scale_points=(catalog.ScalePoint("small", why="w", expected_workload=1),),
            workload_unit="things",
            setup=setup,
            run=run_flow,
            verify=verify,
        )

        with _child_environment(flow, []), _captured_stdout():
            run_query_doctor.diagnose_in_child(flow.name, "small")

        self.assertEqual(seen["setup"], ("ctx", "small"))
        self.assertEqual(seen["run"], ("ctx", "small"))
        self.assertEqual(seen["verify"], ("ctx", "small", "artifacts"))


class TestObservedWorkloadIsChecked(SimpleTestCase):
    """The same rule the harness applies: a diagnosis of a scenario that did
    not build explains something else."""

    def _flow_observing(self, observed):
        return _flow(
            workload_unit="things",
            scale_points=(catalog.ScalePoint("small", why="w", expected_workload=7),),
            verify=lambda ctx, size, artifacts: observed,
        )

    def test_a_workload_that_does_not_match_fails(self):
        flow = self._flow_observing(3)
        with (
            _child_environment(flow, []),
            _captured_stdout(),
            self.assertRaises(SystemExit) as raised,
        ):
            run_query_doctor.diagnose_in_child(flow.name, "small")

        message = str(raised.exception)
        self.assertIn("produced 3 things", message)
        self.assertIn("declares 7", message)

    def test_a_matching_workload_is_reported(self):
        flow = self._flow_observing(7)
        with _child_environment(flow, []), _captured_stdout() as stdout:
            run_query_doctor.diagnose_in_child(flow.name, "small")

        self.assertIn("7 things", stdout.getvalue())

    def test_a_flow_without_scale_points_has_no_workload_to_check(self):
        flow = _flow(verify=lambda ctx, size, artifacts: None)
        with _child_environment(flow, []), _captured_stdout() as stdout:
            run_query_doctor.diagnose_in_child(flow.name, None)

        self.assertIn("fake_flow [-]", stdout.getvalue())


class TestReportPlacesItsFindings(SimpleTestCase):
    """A page of prescriptions nobody can place is not a diagnosis: the same
    flow reports differently at each scale point."""

    def _print(self, report, size="small", observed=7):
        flow = _flow(
            workload_unit="things",
            scale_points=(catalog.ScalePoint("small", why="w", expected_workload=7),),
        )
        with _captured_stdout() as stdout:
            run_query_doctor.print_report(flow.name, size, flow, observed, report)
        return stdout.getvalue()

    def test_the_header_names_the_flow_size_and_observed_workload(self):
        output = self._print(_report())
        self.assertIn("fake_flow [small]", output)
        self.assertIn("7 things", output)
        self.assertIn("3 queries", output)

    def test_a_clean_flow_says_so(self):
        self.assertIn("no prescriptions", self._print(_report()))

    def test_prescriptions_are_printed_worst_first(self):
        def prescription(severity, issue, count, description):
            return SimpleNamespace(
                severity=SimpleNamespace(value=severity),
                issue_type=SimpleNamespace(value=issue),
                query_count=count,
                description=description,
                fix_suggestion=f"fix {description}",
                callsite=SimpleNamespace(
                    filepath="models.py", line_number=10, function_name="save"
                ),
            )

        output = self._print(
            _report(
                prescriptions=[
                    prescription("info", "fat_select", 1, "wide"),
                    prescription("warning", "duplicate_query", 2, "repeated"),
                    prescription("critical", "n_plus_one", 40, "fanned out"),
                ]
            )
        )

        self.assertLess(output.index("fanned out"), output.index("repeated"))
        self.assertLess(output.index("repeated"), output.index("wide"))
        self.assertIn("CRITICAL  n_plus_one  (40 queries)", output)
        self.assertIn("fix: fix fanned out", output)
        self.assertIn("at models.py:10 in save", output)


class TestTheBenchmarkRunnerIsUnaffected(SimpleTestCase):
    """Two independent commands. run.py must keep working, and keep measuring
    the same thing, in an environment that has never heard of Query Doctor."""

    def test_run_py_never_mentions_query_doctor(self):
        for filename in ("run.py", "catalog.py", "env.py", "seed.py", "settings.py"):
            with self.subTest(file=filename):
                self.assertNotIn("query_doctor", _source_of(filename))

    def test_no_harness_module_imports_the_diagnostic_runner(self):
        for filename in ("run.py", "catalog.py", "env.py", "seed.py"):
            for node in ast.walk(ast.parse(_source_of(filename))):
                for name in _imported_names(node):
                    with self.subTest(file=filename, imported=name):
                        self.assertNotIn("run_query_doctor", name)

    def test_the_benchmark_runner_runs_without_query_doctor(self):
        """main() end to end with the executions faked, in an environment where
        importing Query Doctor raises."""
        attempted = []

        def fake_execute(name, size, template, directory, index, token):
            attempted.append((name, size))
            return {
                "process": name,
                "size": size,
                "queries": 1,
                "seconds": 0.0,
                "workload_unit": None,
                "expected_workload": None,
                "observed_workload": None,
            }

        with (
            query_doctor_missing(),
            mock.patch.object(run, "_build_template", return_value="template"),
            mock.patch.object(run, "execute", side_effect=fake_execute),
            mock.patch.object(sys, "argv", ["run.py", run.ALL]),
            mock.patch("sys.stdout"),
            mock.patch("sys.stderr"),
        ):
            code = run.main()

        self.assertEqual(code, 0)
        self.assertEqual(len(attempted), len(catalog.executions()))

    def test_the_diagnostic_runner_reuses_the_harness_rather_than_copying_it(self):
        """Selection, ownership and the template come from run.py. If they were
        restated here they could drift, and the two commands would stop
        describing the same executions."""
        source = _source_of("run_query_doctor.py")
        for attribute in (
            "run._executions_for",
            "run._select",
            "run._own_directory",
            "run._build_template",
            "run.guard_database",
        ):
            with self.subTest(attribute=attribute):
                self.assertIn(attribute, source)


class TestSingleModuleIdentity(SimpleTestCase):
    def test_the_runner_is_package_qualified(self):
        self.assertTrue(run_query_doctor.__name__.startswith("benchmarks."))

    def test_it_imports_no_sibling_by_bare_name(self):
        siblings = {"catalog", "env", "run", "seed", "settings"}
        for node in ast.walk(ast.parse(_source_of("run_query_doctor.py"))):
            for name in _imported_names(node):
                with self.subTest(imported=name):
                    self.assertNotIn(name.split(".")[0], siblings)
