import unittest
from dataclasses import replace
from decimal import Decimal, localcontext

from marketlab.depth import Level
from marketlab.replay import CASH_BUFFER, WALLET, WINDOWS, Window, replay


D = Decimal


class ReplayTests(unittest.TestCase):
    def test_fixed_arrival_order_across_the_four_policies(self):
        cases = (
            (11, 6, [0, 6, 6, 2], "10.74", "3.26"),
            (28, 6, [0, 6, 6, 3], "11.61", "3.39"),
            (11, 14, [0, 12, 2, 0], "10.42", "3.58"),
            (28, 14, [0, 15, 15, 3], "25.95", "7.05"),
        )
        for total, trial, expected, expected_debit, expected_net in cases:
            with self.subTest(total=total, trial=trial):
                steps = replay(total, trial)
                self.assertEqual([s.trial for s in steps], [w.trial for w in WINDOWS])
                sizes = [s.simulated_fill.quantity for s in steps]
                debit = sum(s.simulated_fill.debit for s in steps)
                self.assertEqual(sizes, expected)
                self.assertEqual(debit, D(expected_debit))
                self.assertEqual(sum(sizes) - debit, D(expected_net))

    def test_withdrawal_and_better_book_cannot_change_submitted_size(self):
        heron = WINDOWS[0]
        immediate = replay(28, 14, (heron,), immediate=True)[0]
        late = replay(28, 14, (heron,))[0]
        self.assertEqual((immediate.requested, late.requested), (11, 11))
        self.assertEqual((immediate.simulated_fill.quantity, late.simulated_fill.quantity), (11, 0))
        scarce = replace(heron, decision_asks=(Level(D(".74"), 2),),
                         arrival_asks=(Level(D(".67"), 30),))
        improved = replay(28, 14, (scarce,))[0]
        self.assertEqual((improved.requested, improved.simulated_fill.quantity), (2, 2))
        self.assertEqual(improved.simulated_fill.debit, D("1.38"))
        expensive = replace(scarce, arrival_asks=(Level(D(".89"), 5),))
        self.assertEqual(replay(28, 14, (expensive,))[0].simulated_fill.quantity, 0)

    def test_report_must_be_received_by_the_decision(self):
        trial = WINDOWS[1]
        late = replace(trial, pass_received=trial.decision_at + 1)
        self.assertEqual(replay(28, 14, (late,))[0].requested, 0)
        on_time = replace(trial, pass_received=trial.decision_at)
        self.assertEqual(replay(28, 14, (on_time,))[0].requested, 15)

    def test_each_cap_includes_fees_and_survives_repeated_trial(self):
        offers = (Level(D(".88"), 100),)
        first = Window("Bell", 0, 1, 4, offers, offers)
        followup = replace(first, decision_at=6, arrives_at=9)
        other = replace(first, trial="Drum", decision_at=12, arrives_at=15)
        steps = replay(80, 16, (first, followup, other))
        self.assertEqual([s.simulated_fill.quantity for s in steps], [17, 0, 13])
        debit = sum(s.simulated_fill.debit for s in steps)
        self.assertEqual(debit, WALLET - CASH_BUFFER)
        for total, per_trial in [(0, 16), (80, 0)]:
            self.assertEqual(replay(total, per_trial, (first,))[0].requested, 0)

    def test_terminated_order_releases_unused_reserve_on_same_trial(self):
        first = WINDOWS[0]
        fresh = replace(first, decision_at=12, arrives_at=15,
                        arrival_asks=(Level(D(".78"), 2),))
        steps = replay(28, 14, (first, fresh))
        self.assertEqual([s.requested for s in steps], [11, 11])
        self.assertEqual([s.simulated_fill.quantity for s in steps], [0, 2])

    def test_rejects_duplicate_reordered_or_overlapping_windows(self):
        first, second = WINDOWS[:2]
        for tape in [(first, first), (second, first),
                     (first, replace(second, decision_at=first.arrives_at))]:
            with self.subTest(tape=tape), self.assertRaises(ValueError):
                replay(28, 14, tape)
        for total, trial in [(True, 6), (11, -1)]:
            with self.assertRaises(ValueError):
                replay(total, trial)

    def test_missing_identity_cannot_group_unrelated_trial_budgets(self):
        for name in (None, "", "   "):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "identity"):
                replay(28, 14, (replace(WINDOWS[0], trial=name),))

    def test_summary_math_is_independent_of_callers_decimal_precision(self):
        with localcontext() as ctx:
            ctx.prec = 2
            steps = replay(28, 14)
            self.assertEqual(steps[1].simulated_fill.debit, D("11.34"))
            self.assertEqual(steps[2].simulated_fill.quantity, 15)


if __name__ == "__main__":
    unittest.main()
