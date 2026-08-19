"""Structural tests for the attribution runner.

The runner is a manual diagnostic tool, so these tests attribute nothing real.
They cover the parts that decide whether a report can be believed: that a shape
collapses only what is volatile, that a group keeps the widths its shape hides,
that the totals reconcile against the harness's own counter, and that a
selection this command cannot attribute is refused before anything is built.

Normalisation is exercised with synthetic statements rather than captured SQL.
Real SQL changes when Django or Wagtail change how they build a query, and a
test pinned to today's output would fail on an upgrade that broke nothing.
"""

import contextlib
import io
import json
import os
import sys
import tempfile

from unittest import mock

from django.test import SimpleTestCase

from benchmarks import catalog, run, run_attribution


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _point(label, expected_workload, **overrides):
    fields = {"label": label, "why": "w", "expected_workload": expected_workload}
    fields.update(overrides)
    return catalog.ScalePoint(**fields)


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
        "workload_unit": "widgets",
        "scale_points": (_point("small", 2), _point("large", 40)),
    }
    fields.update(overrides)
    return catalog.Flow(**fields)


def _event(shape="SELECT 1", frame="models.py:1 in f", stack=None, **overrides):
    fields = {
        "shape": shape,
        "kind": "query",
        "stack": [frame] if stack is None else stack,
        "in_arity": None,
        "batch": None,
    }
    fields.update(overrides)
    return fields


def _execution(events, observed_workload, total=None):
    return {
        "size": "small",
        "observed_workload": observed_workload,
        "total": len(events) if total is None else total,
        "events": events,
    }


@contextlib.contextmanager
def _captured_stdout():
    stream = io.StringIO()
    with mock.patch.object(sys, "stdout", stream):
        yield stream


# ---------------------------------------------------------------------------
# Shapes
# ---------------------------------------------------------------------------


class TestShapeCollapsesOnlyWhatIsVolatile(SimpleTestCase):
    def test_an_in_list_collapses_whatever_its_width(self):
        two = run_attribution.shape('SELECT * FROM t WHERE "id" IN (%s, %s)')
        placeholders = ", ".join(["%s"] * 40)
        forty = run_attribution.shape(
            f'SELECT * FROM t WHERE "id" IN ({placeholders})'  # noqa: S608
        )
        self.assertEqual(two, forty)

    def test_not_in_collapses_too_and_stays_distinct_from_in(self):
        inside = run_attribution.shape("SELECT * FROM t WHERE a IN (%s, %s)")
        outside = run_attribution.shape("SELECT * FROM t WHERE a NOT IN (%s, %s)")
        self.assertNotEqual(inside, outside)
        self.assertIn("NOT IN", outside)

    def test_a_values_list_keeps_every_placeholder(self):
        """An insert of three columns and one of five are different statements.
        Collapsing their placeholder lists the way an IN list is collapsed would
        merge them into one shape."""
        self.assertEqual(
            run_attribution.shape("INSERT INTO t (a, b, c) VALUES (%s, %s, %s)"),
            "INSERT INTO t (a, b, c) VALUES (%s, %s, %s)",
        )

    def test_a_function_argument_list_keeps_every_placeholder(self):
        self.assertEqual(
            run_attribution.shape("SELECT coalesce(%s, %s, %s) FROM t"),
            "SELECT coalesce(%s, %s, %s) FROM t",
        )

    def test_savepoint_identifiers_collapse(self):
        first = run_attribution.shape('SAVEPOINT "s140234_x1"')
        second = run_attribution.shape('SAVEPOINT "s140987_x9"')
        self.assertEqual(first, second)
        self.assertEqual(first, "SAVEPOINT")

    def test_release_and_rollback_to_keep_their_own_shapes(self):
        release = run_attribution.shape('RELEASE SAVEPOINT "s1"')
        rollback = run_attribution.shape('ROLLBACK TO SAVEPOINT "s1"')
        self.assertNotEqual(release, rollback)

    def test_whitespace_is_collapsed(self):
        self.assertEqual(
            run_attribution.shape("SELECT\n  a,\n  b\nFROM   t"),
            "SELECT a, b FROM t",
        )

    def test_numeric_literals_are_left_alone(self):
        """Django inlines structural numbers, and LIMIT 1 versus LIMIT 21 is the
        difference between .get() and a sliced queryset."""
        one = run_attribution.shape("SELECT a FROM t LIMIT 1")
        many = run_attribution.shape("SELECT a FROM t LIMIT 21")
        self.assertNotEqual(one, many)


class TestArityIsMeasuredNotCollapsed(SimpleTestCase):
    def test_an_in_list_reports_its_width(self):
        self.assertEqual(
            run_attribution.in_arity("SELECT * FROM t WHERE a IN (%s, %s, %s)"), 3
        )

    def test_a_statement_without_an_in_list_reports_nothing(self):
        self.assertIsNone(run_attribution.in_arity("SELECT * FROM t WHERE a = %s"))

    def test_several_in_lists_are_summed(self):
        self.assertEqual(
            run_attribution.in_arity(
                "SELECT * FROM t WHERE a IN (%s, %s) AND b IN (%s, %s, %s)"
            ),
            5,
        )


class TestKindSeparatesTransactionControl(SimpleTestCase):
    def test_a_plain_statement_is_a_query(self):
        self.assertEqual(run_attribution.kind("SELECT 1"), "query")

    def test_commit_and_begin_are_transaction_control(self):
        self.assertEqual(run_attribution.kind("COMMIT"), "transaction")
        self.assertEqual(run_attribution.kind("BEGIN"), "transaction")

    def test_savepoints_are_their_own_kind(self):
        self.assertEqual(run_attribution.kind('SAVEPOINT "s1"'), "savepoint")
        self.assertEqual(run_attribution.kind('RELEASE SAVEPOINT "s1"'), "savepoint")

    def test_rollback_to_savepoint_is_not_a_rollback(self):
        """One undoes part of a transaction and the other undoes all of it."""
        self.assertEqual(
            run_attribution.kind('ROLLBACK TO SAVEPOINT "s1"'), "savepoint"
        )
        self.assertEqual(run_attribution.kind("ROLLBACK"), "transaction")


class TestBatchSizeIsNeverPaidFor(SimpleTestCase):
    def test_a_single_execution_has_no_batch(self):
        self.assertIsNone(run_attribution.batch_size([1, 2, 3], many=False))

    def test_no_parameters_have_no_batch(self):
        self.assertIsNone(run_attribution.batch_size(None, many=True))

    def test_a_sized_sequence_reports_its_length(self):
        self.assertEqual(run_attribution.batch_size([(1,), (2,)], many=True), 2)

    def test_an_iterator_is_reported_as_unknown_and_not_consumed(self):
        """DB-API allows executemany() an iterable without __len__. Counting it
        here would empty it before the driver saw it."""
        params = iter([(1,), (2,), (3,)])
        self.assertIsNone(run_attribution.batch_size(params, many=True))
        self.assertEqual(list(params), [(1,), (2,), (3,)])


# ---------------------------------------------------------------------------
# Stacks
# ---------------------------------------------------------------------------


class TestTheProductStack(SimpleTestCase):
    def test_a_call_from_outside_the_product_finds_no_frame(self):
        self.assertEqual(run_attribution.product_stack(), [])

    def test_frames_are_nearest_first_and_named_by_module_line_and_function(self):
        # This file stands in for the product, so its own frames qualify.
        with mock.patch.object(run_attribution, "_PRODUCT", f"{os.sep}tests{os.sep}"):

            def inner():
                return run_attribution.product_stack()

            def outer():
                return inner()

            frames = outer()

        self.assertTrue(frames[0].startswith("test_benchmarks_attribution.py:"))
        self.assertIn(" in inner", frames[0])
        self.assertIn(" in outer", frames[1])

    def test_no_more_frames_are_kept_than_the_depth_allows(self):
        with (
            mock.patch.object(run_attribution, "_PRODUCT", f"{os.sep}tests{os.sep}"),
            mock.patch.object(run_attribution, "STACK_DEPTH", 2),
        ):

            def a():
                return run_attribution.product_stack()

            def b():
                return a()

            def c():
                return b()

            frames = c()

        self.assertEqual(len(frames), 2)


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------


class TestGroupingKeepsShapeAndFrameApart(SimpleTestCase):
    def test_the_same_shape_from_two_frames_is_two_groups(self):
        grouped = run_attribution.group(
            _execution(
                [
                    _event(shape="SELECT 1", frame="a.py:1 in f"),
                    _event(shape="SELECT 1", frame="b.py:2 in g"),
                ],
                observed_workload=1,
            )
        )
        self.assertEqual(len(grouped), 2)

    def test_two_shapes_from_one_frame_are_two_groups(self):
        grouped = run_attribution.group(
            _execution(
                [
                    _event(shape="SELECT 1", frame="a.py:1 in f"),
                    _event(shape="SELECT 2", frame="a.py:1 in f"),
                ],
                observed_workload=1,
            )
        )
        self.assertEqual(len(grouped), 2)

    def test_repetitions_of_one_group_are_counted(self):
        grouped = run_attribution.group(
            _execution([_event(), _event(), _event()], observed_workload=1)
        )
        self.assertEqual(next(iter(grouped.values()))["count"], 3)

    def test_an_event_with_no_product_frame_is_named_rather_than_dropped(self):
        grouped = run_attribution.group(
            _execution([_event(stack=[])], observed_workload=1)
        )
        key = next(iter(grouped))
        self.assertEqual(key[1], run_attribution.OUTSIDE)


class TestAGroupKeepsTheWidthsItsShapeHides(SimpleTestCase):
    def test_arity_is_reported_as_the_range_the_group_covered(self):
        grouped = run_attribution.group(
            _execution(
                [_event(in_arity=2), _event(in_arity=40), _event(in_arity=7)],
                observed_workload=1,
            )
        )
        self.assertEqual(next(iter(grouped.values()))["in_arity"], [2, 40])

    def test_a_group_whose_events_carry_no_width_reports_none(self):
        grouped = run_attribution.group(_execution([_event()], observed_workload=1))
        entry = next(iter(grouped.values()))
        self.assertIsNone(entry["in_arity"])
        self.assertIsNone(entry["batch"])

    def test_an_unknown_batch_does_not_hide_a_known_one(self):
        grouped = run_attribution.group(
            _execution([_event(batch=None), _event(batch=5)], observed_workload=1)
        )
        self.assertEqual(next(iter(grouped.values()))["batch"], [5, 5])

    def test_the_kind_of_a_group_is_kept(self):
        grouped = run_attribution.group(
            _execution(
                [_event(shape="COMMIT", kind="transaction")], observed_workload=1
            )
        )
        self.assertEqual(next(iter(grouped.values()))["kind"], "transaction")


class TestCallersAreKept(SimpleTestCase):
    def test_the_frames_above_the_nearest_one_are_reported_per_caller(self):
        grouped = run_attribution.group(
            _execution(
                [
                    _event(stack=["a.py:1 in f", "b.py:2 in g"]),
                    _event(stack=["a.py:1 in f", "b.py:2 in g"]),
                    _event(stack=["a.py:1 in f", "c.py:3 in h"]),
                ],
                observed_workload=1,
            )
        )
        callers = next(iter(grouped.values()))["callers"]
        self.assertEqual(callers["b.py:2 in g"], 2)
        self.assertEqual(callers["c.py:3 in h"], 1)

    def test_no_more_callers_are_kept_than_the_cap_allows(self):
        events = [
            _event(stack=["a.py:1 in f", f"caller{index}.py:1 in g"])
            for index in range(run_attribution.CALLERS + 3)
        ]
        grouped = run_attribution.group(_execution(events, observed_workload=1))
        callers = next(iter(grouped.values()))["callers"]
        self.assertEqual(len(callers), run_attribution.CALLERS)


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconciliationAgainstTheHarnessCounter(SimpleTestCase):
    def test_a_flow_without_transactions_leaves_nothing_unattributed(self):
        execution = _execution([_event(), _event()], observed_workload=1, total=2)
        self.assertEqual(run_attribution.unattributed(execution), 0)

    def test_statements_the_wrapper_cannot_see_are_counted_not_dropped(self):
        """Django's _commit() calls the connection directly and appends a
        synthetic record to the query log, so the harness counts what no
        wrapper runs for."""
        execution = _execution([_event(), _event()], observed_workload=1, total=6)
        self.assertEqual(run_attribution.unattributed(execution), 4)

    def test_the_report_states_the_split(self):
        flow = _flow()
        small = _execution([_event()], observed_workload=2, total=5)
        large = _execution([_event(), _event()], observed_workload=40, total=6)
        rows = run_attribution.build(small, large)

        with _captured_stdout() as stream:
            run_attribution.print_report(flow.name, flow, small, large, rows)

        printed = stream.getvalue()
        self.assertIn("5 queries  = 1 attributed + 4 outside", printed)
        self.assertIn("6 queries  = 2 attributed + 4 outside", printed)


# ---------------------------------------------------------------------------
# Rates
# ---------------------------------------------------------------------------


class TestRatesComeFromTheDeclaredWorkload(SimpleTestCase):
    def _rows(self, small_events, large_events, small_workload=2, large_workload=40):
        return run_attribution.build(
            _execution(small_events, observed_workload=small_workload),
            _execution(large_events, observed_workload=large_workload),
        )

    def test_a_group_growing_one_per_unit_has_a_rate_of_one(self):
        rows = self._rows([_event()] * 2, [_event()] * 40)
        self.assertAlmostEqual(rows[0]["rate"], 1.0)

    def test_a_group_that_does_not_grow_has_a_rate_of_zero(self):
        rows = self._rows([_event()], [_event()])
        self.assertAlmostEqual(rows[0]["rate"], 0.0)

    def test_a_group_present_at_only_one_size_still_appears(self):
        rows = self._rows([_event(shape="SELECT 1")], [_event(shape="SELECT 2")])
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["delta"] for row in rows}, {1, -1})

    def test_the_fixed_estimate_is_what_the_two_counts_imply_at_zero(self):
        # 2 -> 40 over a workload of 2 -> 40 is one per unit through the origin.
        rows = self._rows([_event()] * 2, [_event()] * 40)
        self.assertAlmostEqual(rows[0]["fixed"], 0.0)

    def test_a_group_that_skips_part_of_the_workload_shows_it(self):
        # One event fewer at each size than the workload: a group that runs for
        # all but one unit.
        rows = self._rows([_event()] * 1, [_event()] * 39)
        self.assertAlmostEqual(rows[0]["rate"], 1.0)
        self.assertAlmostEqual(rows[0]["fixed"], -1.0)

    def test_rows_are_ranked_by_how_much_they_grew(self):
        rows = self._rows(
            [_event(shape="SLOW"), _event(shape="FLAT")],
            [_event(shape="SLOW")] * 40 + [_event(shape="FLAT")],
        )
        self.assertEqual(rows[0]["shape"], "SLOW")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


class TestTheReportDisclosesWhatItHides(SimpleTestCase):
    def _print(self, small_events, large_events):
        flow = _flow()
        small = _execution(small_events, observed_workload=2)
        large = _execution(large_events, observed_workload=40)
        rows = run_attribution.build(small, large)
        with _captured_stdout() as stream:
            run_attribution.print_report(flow.name, flow, small, large, rows)
        return stream.getvalue()

    def test_the_header_names_the_flow_and_both_workloads(self):
        printed = self._print([_event()], [_event()])
        self.assertIn("fake_flow: 2 -> 40 widgets", printed)

    def test_groups_that_shrank_are_listed_separately(self):
        printed = self._print([_event(shape="GONE")] * 3, [_event(shape="GONE")])
        self.assertIn("Groups that shrank", printed)

    def test_a_tail_it_does_not_print_is_summarised(self):
        # One driver covers the coverage cut, so the smaller growing groups
        # behind it are summarised rather than listed.
        small = [_event(shape="BIG")] * 2 + [
            _event(shape=f"UP{index}") for index in range(3)
        ]
        large = [_event(shape="BIG")] * 300 + [
            _event(shape=f"UP{index}") for index in range(3) for _ in range(4)
        ]
        printed = self._print(small, large)
        self.assertIn("3 further changed group(s) not shown", printed)
        self.assertIn("net +9", printed)
        self.assertIn("gross movement 9", printed)

    def test_a_group_that_shrank_is_not_also_counted_as_hidden(self):
        """It is printed in its own section, so calling it unseen would tell a
        reader something is hidden that they have just read."""
        small = [_event(shape="BIG")] * 2 + [_event(shape="DOWN")] * 6
        large = [_event(shape="BIG")] * 300 + [_event(shape="DOWN")]
        printed = self._print(small, large)
        self.assertIn("Groups that shrank", printed)
        self.assertNotIn("further changed group(s) not shown", printed)

    def test_a_width_the_shape_hides_is_shown_beside_it(self):
        printed = self._print(
            [_event(in_arity=2)],
            [_event(in_arity=40)] * 2,
        )
        self.assertIn("[IN arity 2 -> 40]", printed)

    def test_a_group_with_no_width_carries_no_note(self):
        printed = self._print([_event()], [_event()] * 2)
        self.assertNotIn("[IN arity", printed)
        self.assertNotIn("[batch", printed)


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


class TestSelectionIsRefusedEarly(SimpleTestCase):
    def _main(self, *argv):
        with mock.patch.object(sys, "argv", ["run_attribution.py", *argv]):
            return run_attribution.main()

    def test_an_unknown_flow_names_the_known_ones(self):
        with (
            _captured_stdout(),
            contextlib.redirect_stderr(io.StringIO()) as stderr,
            self.assertRaises(SystemExit),
        ):
            self._main("no_such_flow")
        self.assertIn("core_page_index", stderr.getvalue())

    def test_a_flow_without_two_scale_points_is_refused_before_anything_is_built(self):
        flow = _flow(scale_points=())
        with (
            mock.patch.dict(catalog.BY_NAME, {flow.name: flow}),
            mock.patch.object(run, "_build_template") as template,
            self.assertRaises(SystemExit) as raised,
        ):
            self._main(flow.name)

        self.assertIn("0 scale point", str(raised.exception))
        template.assert_not_called()

    def test_a_flow_with_one_scale_point_is_refused_too(self):
        flow = _flow(scale_points=(_point("only", 3),))
        with (
            mock.patch.dict(catalog.BY_NAME, {flow.name: flow}),
            self.assertRaises(SystemExit) as raised,
        ):
            self._main(flow.name)

        self.assertIn("1 scale point", str(raised.exception))

    def test_no_flow_and_no_list_is_refused(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self._main()

    def test_listing_prints_the_catalog_without_building_anything(self):
        with (
            mock.patch.object(run, "_build_template") as template,
            _captured_stdout() as stream,
        ):
            self.assertEqual(self._main("--list"), 0)

        self.assertIn("core_page_index", stream.getvalue())
        template.assert_not_called()


# ---------------------------------------------------------------------------
# The instrumented region
# ---------------------------------------------------------------------------


class TestTheAttributedRegion(SimpleTestCase):
    """What the child instruments, and what it refuses to report."""

    @contextlib.contextmanager
    def _child(self, flow, events):
        captured = []

        class FakeCapture:
            def __init__(self, connection):
                pass

            def __enter__(self):
                events.append("capture:enter")
                return captured

            def __exit__(self, *exc):
                events.append("capture:exit")
                return False

        def fake_prepare():
            events.append("prepare")
            return "ctx"

        with (
            mock.patch.object(run, "guard_database", return_value="db"),
            mock.patch.dict(catalog.BY_NAME, {flow.name: flow}),
            mock.patch.object(catalog, "prepare", side_effect=fake_prepare),
            mock.patch("benchmarks.env.bootstrap"),
            mock.patch("django.test.utils.CaptureQueriesContext", FakeCapture),
        ):
            yield

    def _run_child(self, flow, events, size="small"):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "events.json")
            with (
                self._child(flow, events),
                mock.patch.dict(os.environ, {run_attribution.EVENTS_ENV_VAR: path}),
            ):
                run_attribution.attribute_in_child(flow.name, size)
            with open(path) as handle:
                return json.load(handle)

    def test_prepare_setup_run_and_verify_happen_around_the_capture(self):
        events = []
        flow = _flow(
            setup=lambda ctx, size: events.append("setup"),
            run=lambda ctx, size: events.append("run") or "artifacts",
            verify=lambda ctx, size, artifacts: events.append("verify") or 2,
        )
        self._run_child(flow, events)

        self.assertEqual(
            events,
            ["prepare", "setup", "capture:enter", "run", "capture:exit", "verify"],
        )

    def test_a_workload_that_does_not_match_the_scale_point_fails(self):
        events = []
        flow = _flow(verify=lambda ctx, size, artifacts: 99)
        with self.assertRaises(SystemExit) as raised:
            self._run_child(flow, events)

        self.assertIn("99", str(raised.exception))
        self.assertIn("2", str(raised.exception))

    def test_the_observed_workload_is_written_out(self):
        events = []
        flow = _flow(verify=lambda ctx, size, artifacts: 2)
        written = self._run_child(flow, events)
        self.assertEqual(written["observed_workload"], 2)
        self.assertEqual(written["size"], "small")


# ---------------------------------------------------------------------------
# Separation from the harness
# ---------------------------------------------------------------------------


class TestTheBenchmarkRunnerIsUnaffected(SimpleTestCase):
    def test_run_py_never_mentions_the_attribution_runner(self):
        with open(run.__file__) as handle:
            self.assertNotIn("run_attribution", handle.read())

    def test_the_attribution_runner_reuses_the_harness_rather_than_copying_it(self):
        with open(run_attribution.__file__) as handle:
            source = handle.read()
        for helper in ("_own_directory", "_build_template", "guard_database"):
            self.assertIn(f"run.{helper}", source)
