import unittest
from fractions import Fraction

from marketlab.cohorts import ExitAllocation, Flow, analyse


class CohortTests(unittest.TestCase):
    def test_partial_exit_spans_two_cohorts_with_different_deadlines(self):
        events = [
            Flow(0, "A", "entry", 6), Flow(4, "A", "entry", 4),
            Flow(5, "A", "normal", 4), Flow(6, "A", "repair", 1),
            Flow(11, "A", "normal", 3), Flow(18, "A", "entry", 2),
        ]
        report = analyse(events, as_of=20, horizon=10)
        self.assertEqual(report.cohorts[0].exits, (
            ExitAllocation(5, "normal", 4), ExitAllocation(6, "repair", 1),
            ExitAllocation(11, "normal", 1),
        ))
        self.assertEqual(report.cohorts[1].exits, (ExitAllocation(11, "normal", 2),))
        self.assertEqual(report.mature_quantity, 10)
        self.assertEqual(report.normal_by_horizon, 6)
        self.assertEqual(report.repair_by_horizon, 1)
        self.assertEqual(report.unexited_by_horizon, 3)
        self.assertEqual(report.too_young_quantity, 2)
        self.assertEqual(report.normal_exit_fraction, Fraction(3, 5))

    def test_future_exit_and_future_entry_do_not_affect_current_snapshot(self):
        initial = [Flow(1, "A", "entry", 2)]
        report = analyse(initial, as_of=10, horizon=9)
        extended = initial + [Flow(12, "A", "normal", 2), Flow(13, "A", "entry", 3)]
        self.assertEqual(analyse(extended, as_of=10, horizon=9), report)
        self.assertEqual(report.normal_exit_fraction, 0)
        self.assertEqual(report.unexited_by_horizon, 2)
        self.assertEqual(report.cohorts[0].exits, ())

    def test_young_early_exit_does_not_inflate_mature_fraction(self):
        events = [Flow(0, "A", "entry", 2), Flow(9, "B", "entry", 9),
                  Flow(10, "B", "normal", 9)]
        report = analyse(events, as_of=10, horizon=10)
        self.assertEqual(report.normal_exit_fraction, 0)
        self.assertEqual(report.unexited_by_horizon, 2)
        self.assertEqual(report.too_young_quantity, 9)

    def test_endpoint_is_inclusive_and_gaps_count_as_calendar_time(self):
        events = [Flow(10, "A", "entry", 2), Flow(110, "A", "normal", 1),
                  Flow(111, "A", "normal", 1)]
        report = analyse(events, as_of=200, horizon=100)
        self.assertEqual(report.normal_exit_fraction, Fraction(1, 2))
        self.assertEqual(report.unexited_by_horizon, 1)

    def test_no_mature_quantity_has_undefined_fraction(self):
        events = [Flow(3, "A", "entry", 8)]
        self.assertIsNone(analyse(events, as_of=5, horizon=9).normal_exit_fraction)
        self.assertIsNone(analyse([], as_of=5, horizon=9).normal_exit_fraction)

    def test_same_second_respects_receipt_order(self):
        first, exit_fill = Flow(0, "A", "entry", 2), Flow(0, "A", "repair", 2)
        self.assertEqual(analyse([first, exit_fill], as_of=0, horizon=0).repair_by_horizon, 2)
        with self.assertRaisesRegex(ValueError, "inventory"):
            analyse([exit_fill, first], as_of=0, horizon=0)

    def test_cannot_consume_another_stream_or_more_than_remaining(self):
        for key, quantity in [("B", 1), ("A", 3)]:
            with self.subTest(key=key, quantity=quantity), self.assertRaisesRegex(ValueError, "inventory"):
                analyse([Flow(0, "A", "entry", 2), Flow(1, key, "normal", quantity)],
                        as_of=10, horizon=5)

    def test_bad_data_is_not_silently_sorted_or_scored(self):
        with self.assertRaisesRegex(ValueError, "chronological"):
            analyse([Flow(2, "A", "entry", 1), Flow(1, "A", "entry", 1)], as_of=5, horizon=2)
        for args in [(1, "", "normal", 3), (1, "A", "order", 3),
                     (1, "A", "entry", True), (-1, "A", "entry", 2)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                Flow(*args)
        with self.assertRaises(ValueError):
            analyse([], as_of=1, horizon=-1)


if __name__ == "__main__":
    unittest.main()
