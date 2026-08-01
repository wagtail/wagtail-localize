"""Structural tests for the benchmark harness."""

import ast
import contextlib
import os
import sys
import tempfile

from unittest import mock

from django.test import SimpleTestCase


BENCHMARKS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"
)

# Import the harness the way `python benchmarks/run.py` does.
if BENCHMARKS not in sys.path:
    sys.path.insert(0, BENCHMARKS)

import catalog  # noqa: E402
import run  # noqa: E402


@contextlib.contextmanager
def environment(**values):
    """Set env vars for the duration of a block, restoring what was there."""
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _source_of(filename):
    with open(os.path.join(BENCHMARKS, filename)) as handle:
        return handle.read()


class TestFlowModel(SimpleTestCase):
    def test_a_flow_without_scale_points_runs_once_with_no_size(self):
        flow = catalog.Flow(
            name="x",
            group="g",
            why="w",
            entrypoint="e",
            covers=(),
            run=lambda ctx, size: None,
            verify=lambda ctx, size, a: None,
        )
        self.assertEqual(flow.sizes(), (None,))
        self.assertIsNone(flow.scale_point(None))

    def test_a_flow_with_scale_points_expands_to_one_execution_each(self):
        flow = catalog.Flow(
            name="x",
            group="g",
            why="w",
            entrypoint="e",
            covers=(),
            run=lambda ctx, size: None,
            verify=lambda ctx, size, a: None,
            workload_unit="things",
            scale_points=(
                catalog.ScalePoint("small", why="w", expected_workload=1),
                catalog.ScalePoint("large", why="w", expected_workload=9),
            ),
        )
        self.assertEqual(flow.sizes(), ("small", "large"))
        self.assertEqual(flow.scale_point("large").expected_workload, 9)
        self.assertIsNone(flow.scale_point("enormous"))


class TestCatalogIntegrity(SimpleTestCase):
    def test_flow_names_are_unique(self):
        names = [flow.name for flow in catalog.CATALOG]
        self.assertEqual(len(names), len(set(names)))

    def test_a_flow_declaring_scale_points_declares_two_or_more(self):
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                self.assertNotEqual(len(flow.scale_points), 1)

    def test_every_scale_point_declares_the_workload_it_expects(self):
        for flow in catalog.CATALOG:
            for point in flow.scale_points:
                with self.subTest(flow=flow.name, size=point.label):
                    self.assertIsInstance(point.expected_workload, int)
                    self.assertGreater(point.expected_workload, 0)

    def test_a_flow_with_scale_points_names_the_unit_they_count(self):
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                if flow.scale_points:
                    self.assertTrue(flow.workload_unit)

    def test_every_flow_is_documented(self):
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                self.assertTrue(flow.why)
                self.assertTrue(flow.entrypoint)
                self.assertTrue(flow.group)

    def test_expected_workload_grows_with_the_scale_points(self):
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                expected = [p.expected_workload for p in flow.scale_points]
                self.assertEqual(expected, sorted(expected))
                self.assertEqual(len(expected), len(set(expected)))

    def test_the_catalog_expands_to_the_executions_it_claims(self):
        expanded = catalog.executions()
        self.assertEqual(len(catalog.CATALOG), 2)
        self.assertEqual(len(expanded), 3)
        self.assertEqual(
            len(expanded), sum(len(flow.sizes()) for flow in catalog.CATALOG)
        )
        self.assertIn((catalog.BY_NAME["edit_translation_get"], "large"), expanded)

    def test_a_flow_without_scale_points_expands_to_a_single_sizeless_execution(self):
        flow = catalog.BY_NAME["submit_page_post"]
        self.assertEqual(flow.scale_points, ())
        self.assertIsNone(flow.workload_unit)
        self.assertEqual(
            [pair for pair in catalog.executions() if pair[0] is flow],
            [(flow, None)],
        )


class TestCatalogNeedsNoDjango(SimpleTestCase):
    def test_the_catalog_module_imports_no_django_at_module_level(self):
        source = ast.parse(_source_of("catalog.py"))
        for node in source.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = getattr(node, "module", "") or ""
                names = [alias.name for alias in node.names]
                self.assertFalse(
                    module.startswith(("django", "wagtail"))
                    or any(n.startswith(("django", "wagtail")) for n in names),
                    f"catalog.py imports {module or names} at module level",
                )


class TestRunnerParentNeverImportsDjango(SimpleTestCase):
    """The parent must not open a Django connection before copying SQLite."""

    def test_run_py_imports_no_django_at_module_level(self):
        source = ast.parse(_source_of("run.py"))
        for node in source.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                module = getattr(node, "module", "") or ""
                names = [alias.name for alias in node.names]
                self.assertFalse(
                    module.startswith(("django", "wagtail", "env", "catalog"))
                    or any(
                        n.startswith(("django", "wagtail", "env", "catalog"))
                        for n in names
                    ),
                    f"run.py imports {module or names} at module level",
                )

    def test_the_parent_code_path_defers_every_django_import(self):
        source = ast.parse(_source_of("run.py"))
        child_side = {"run_in_child", "build_template_in_child"}

        for node in source.body:
            if not isinstance(node, ast.FunctionDef) or node.name in child_side:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Import | ast.ImportFrom):
                    module = getattr(inner, "module", "") or ""
                    names = [alias.name for alias in inner.names]
                    self.assertFalse(
                        module.startswith(("django", "wagtail", "env"))
                        or any(
                            n.startswith(("django", "wagtail", "env")) for n in names
                        ),
                        f"parent function {node.name}() imports {module or names}",
                    )


class TestScalePointLabelsAreUnique(SimpleTestCase):
    def test_no_flow_declares_the_same_label_twice(self):
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                labels = [point.label for point in flow.scale_points]
                self.assertEqual(len(labels), len(set(labels)))


class TestDatabaseGuard(SimpleTestCase):
    """Internal child commands must refuse databases the harness does not own."""

    def test_a_database_outside_a_harness_directory_is_refused(self):
        with tempfile.TemporaryDirectory() as outsider:
            database = os.path.join(outsider, "somebodys-real.sqlite3")
            contents = b"not a real database, and must stay that way"
            with open(database, "wb") as handle:
                handle.write(contents)

            with (
                environment(
                    **{run.DB_ENV_VAR: database, run.TOKEN_ENV_VAR: "any-token"}
                ),
                self.assertRaises(SystemExit) as raised,
            ):
                run.guard_database()

            self.assertIn("refusing to use", str(raised.exception))
            with open(database, "rb") as handle:
                self.assertEqual(handle.read(), contents)

    def test_a_missing_token_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            run._own_directory(directory)
            database = os.path.join(directory, "run-00.sqlite3")

            with (
                environment(**{run.DB_ENV_VAR: database, run.TOKEN_ENV_VAR: None}),
                self.assertRaises(SystemExit) as raised,
            ):
                run.guard_database()

            self.assertIn(run.TOKEN_ENV_VAR, str(raised.exception))

    def test_a_wrong_token_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            run._own_directory(directory)
            database = os.path.join(directory, "run-00.sqlite3")

            with (
                environment(
                    **{run.DB_ENV_VAR: database, run.TOKEN_ENV_VAR: "not-the-token"}
                ),
                self.assertRaises(SystemExit) as raised,
            ):
                run.guard_database()

            self.assertIn("token does not match", str(raised.exception))

    def test_the_harness_own_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            token = run._own_directory(directory)
            database = os.path.join(directory, "run-00.sqlite3")

            with environment(**{run.DB_ENV_VAR: database, run.TOKEN_ENV_VAR: token}):
                self.assertEqual(run.guard_database(), os.path.realpath(database))


class TestChildSelectionGuard(SimpleTestCase):
    def test_an_unknown_flow_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            run._select("no_such_flow", "small")
        self.assertIn("unknown flow", str(raised.exception))

    def test_an_undeclared_size_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            run._select("edit_translation_get", "enormous")
        self.assertIn("no size", str(raised.exception))

    def test_a_flow_with_scale_points_requires_one(self):
        with self.assertRaises(SystemExit) as raised:
            run._select("edit_translation_get", None)
        self.assertIn("needs a size", str(raised.exception))

    def test_a_flow_without_scale_points_is_accepted_without_a_size(self):
        _catalog, flow, point = run._select("submit_page_post", None)
        self.assertEqual(flow.name, "submit_page_post")
        self.assertIsNone(point)

    def test_a_size_on_a_flow_without_scale_points_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            run._select("submit_page_post", "small")
        self.assertIn("takes no size", str(raised.exception))

    def test_a_declared_size_is_accepted(self):
        _catalog, flow, point = run._select("edit_translation_get", "large")
        self.assertEqual(flow.name, "edit_translation_get")
        self.assertEqual(point.expected_workload, 42)


class TestHarnessSettings(SimpleTestCase):
    def test_the_harness_settings_turn_debug_off(self):
        import benchmarks.settings

        self.assertFalse(benchmarks.settings.DEBUG)


class TestReservedCatalogNames(SimpleTestCase):
    def test_no_flow_is_called_all(self):
        self.assertNotIn(run.ALL, catalog.BY_NAME)


class TestExecutionSelection(SimpleTestCase):
    def test_all_selects_the_whole_catalog_in_order(self):
        self.assertEqual(run._executions_for(run.ALL, None), list(catalog.executions()))

    def test_all_refuses_a_size(self):
        with self.assertRaises(ValueError) as raised:
            run._executions_for(run.ALL, "small")
        self.assertIn("cannot be used with all", str(raised.exception))

    def test_a_scaled_flow_without_a_size_selects_every_point(self):
        flow = catalog.BY_NAME["edit_translation_get"]
        self.assertEqual(
            run._executions_for("edit_translation_get", None),
            [(flow, "small"), (flow, "large")],
        )

    def test_a_scaled_flow_with_a_size_selects_only_that_point(self):
        flow = catalog.BY_NAME["edit_translation_get"]
        self.assertEqual(
            run._executions_for("edit_translation_get", "large"), [(flow, "large")]
        )

    def test_a_flow_without_scale_points_selects_one_sizeless_execution(self):
        flow = catalog.BY_NAME["submit_page_post"]
        self.assertEqual(run._executions_for("submit_page_post", None), [(flow, None)])

    def test_a_flow_without_scale_points_refuses_a_size(self):
        with self.assertRaises(ValueError) as raised:
            run._executions_for("submit_page_post", "small")
        self.assertIn("takes no size", str(raised.exception))

    def test_an_unknown_name_lists_the_valid_ones(self):
        with self.assertRaises(ValueError) as raised:
            run._executions_for("no_such_flow", None)
        message = str(raised.exception)
        self.assertIn("edit_translation_get", message)
        self.assertIn(run.ALL, message)


class TestOrchestration(SimpleTestCase):
    """A failing execution must not stop the ones after it."""

    def _run_all(self, failing_index):
        attempted = []

        def fake_execute(name, size, template, directory, index, token):
            attempted.append((name, size))
            if index == failing_index:
                return {"process": name, "size": size, "error": "deliberate"}
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
            mock.patch.object(run, "_build_template", return_value="template"),
            mock.patch.object(run, "execute", side_effect=fake_execute),
            mock.patch.object(sys, "argv", ["run.py", run.ALL]),
            mock.patch("sys.stdout"),
            mock.patch("sys.stderr"),
        ):
            return run.main(), attempted

    def test_every_execution_is_attempted_and_the_run_reports_failure(self):
        code, attempted = self._run_all(failing_index=0)
        self.assertEqual(code, 1)
        self.assertEqual(len(attempted), len(catalog.executions()))

    def test_a_run_with_no_failures_reports_success(self):
        code, attempted = self._run_all(failing_index=None)
        self.assertEqual(code, 0)
        self.assertEqual(len(attempted), len(catalog.executions()))
