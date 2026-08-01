"""Structural tests for the benchmark harness."""

import ast
import contextlib
import os
import sys
import tempfile

from unittest import mock

from django.test import SimpleTestCase

from benchmarks import catalog, run


BENCHMARKS = os.path.dirname(os.path.abspath(run.__file__))


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


DJANGO = ("django", "wagtail")
# Any harness sibling. Forbidden at module level in run.py, where importing one
# would run its imports too; allowed inside parent functions when the sibling is
# Django-free, which benchmarks.catalog is and benchmarks.env is not.
HARNESS = ("benchmarks",)
BOOTSTRAP = (*DJANGO, "benchmarks.env", "benchmarks.settings")


def _source_of(filename):
    with open(os.path.join(BENCHMARKS, filename)) as handle:
        return handle.read()


def _imported_names(node):
    """Every module path an import node names, or () if it is not an import.

    `from benchmarks import env` and `from benchmarks.env import bootstrap`
    both have to be read as naming benchmarks.env, and one statement can carry
    several aliases.
    """
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        module = node.module or ""
        return (module, *(f"{module}.{alias.name}" for alias in node.names))
    return ()


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
        for node in ast.parse(_source_of("catalog.py")).body:
            for name in _imported_names(node):
                self.assertFalse(
                    name.startswith(DJANGO),
                    f"catalog.py imports {name} at module level",
                )


class TestRunnerParentNeverImportsDjango(SimpleTestCase):
    """The parent must not open a Django connection before copying SQLite."""

    def test_run_py_imports_no_django_at_module_level(self):
        for node in ast.parse(_source_of("run.py")).body:
            for name in _imported_names(node):
                self.assertFalse(
                    name.startswith(DJANGO + HARNESS),
                    f"run.py imports {name} at module level",
                )

    def test_the_parent_code_path_defers_every_django_import(self):
        source = ast.parse(_source_of("run.py"))
        child_side = {"run_in_child", "build_template_in_child"}

        for node in source.body:
            if not isinstance(node, ast.FunctionDef) or node.name in child_side:
                continue
            for inner in ast.walk(node):
                for name in _imported_names(inner):
                    self.assertFalse(
                        name.startswith(BOOTSTRAP),
                        f"parent function {node.name}() imports {name}",
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


class TestSingleModuleIdentity(SimpleTestCase):
    """Loaded flat and as a package, a harness module becomes two objects with
    separate state. Everything imports it one way."""

    def test_the_harness_modules_are_package_qualified(self):
        for module in (catalog, run):
            with self.subTest(module=module.__name__):
                self.assertTrue(module.__name__.startswith("benchmarks."))

    def test_no_harness_module_imports_a_sibling_by_bare_name(self):
        siblings = {"catalog", "env", "run", "seed", "settings"}
        for filename in ("run.py", "catalog.py", "env.py", "seed.py"):
            for node in ast.walk(ast.parse(_source_of(filename))):
                for name in _imported_names(node):
                    with self.subTest(file=filename, imported=name):
                        self.assertNotIn(name.split(".")[0], siblings)


class TestCatalogInvariants(SimpleTestCase):
    def test_a_flow_declaring_a_workload_unit_declares_scale_points(self):
        """Without scale points there is no expected_workload to compare an
        observed one against, so the unit would measure nothing."""
        for flow in catalog.CATALOG:
            with self.subTest(flow=flow.name):
                if flow.workload_unit:
                    self.assertTrue(flow.scale_points)


class TestUnusableChildResult(SimpleTestCase):
    """A child that prints something the parent cannot read is that execution's
    failure. The run continues and ends non-zero."""

    def _execute_with_stdout(self, stdout):
        completed = mock.Mock(returncode=0, stdout=stdout, stderr="")
        with (
            mock.patch.object(run, "_child", return_value=completed),
            mock.patch("shutil.copy"),
        ):
            return run.execute(
                "a_flow", None, "template", "unused-directory", 0, "token"
            )

    def test_malformed_json_becomes_a_failed_result(self):
        result = self._execute_with_stdout(f"{run.RESULT_PREFIX}{{not json")
        self.assertIn("error", result)
        self.assertNotIn("queries", result)

    def test_a_result_missing_a_field_becomes_a_failed_result(self):
        result = self._execute_with_stdout(f'{run.RESULT_PREFIX}{{"pid": 1}}')
        self.assertIn("error", result)

    def test_a_json_value_that_is_not_an_object_becomes_a_failed_result(self):
        result = self._execute_with_stdout(f"{run.RESULT_PREFIX}[1, 2, 3]")
        self.assertIn("error", result)

    def test_a_well_formed_result_is_returned(self):
        payload = (
            '{"pid": 1, "database": "d", "queries": 7, "seconds": 0.5, '
            '"observed_workload": null, "expected_workload": null, '
            '"workload_unit": null}'
        )
        result = self._execute_with_stdout(run.RESULT_PREFIX + payload)
        self.assertNotIn("error", result)
        self.assertEqual(result["queries"], 7)

    def test_an_unusable_result_does_not_stop_the_rest_of_the_run(self):
        attempted = []

        def fake_child(args, database, token):
            attempted.append(args)
            return mock.Mock(
                returncode=0, stdout=f"{run.RESULT_PREFIX}{{broken", stderr=""
            )

        with (
            mock.patch.object(run, "_build_template", return_value="template"),
            mock.patch.object(run, "_child", side_effect=fake_child),
            mock.patch("shutil.copy"),
            mock.patch.object(sys, "argv", ["run.py", run.ALL]),
            mock.patch("sys.stdout"),
            mock.patch("sys.stderr"),
        ):
            code = run.main()

        self.assertEqual(code, 1)
        self.assertEqual(len(attempted), len(catalog.executions()))
