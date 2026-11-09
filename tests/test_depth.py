import unittest
from decimal import Decimal, localcontext
from itertools import product

from marketlab.depth import Level, plan_pair, settlement, sweep


D = Decimal


class SweepTests(unittest.TestCase):
    def test_walks_levels_in_price_order_and_accounts_for_fees(self):
        asks = [Level(D(".38"), 3), Level(D(".22"), 3)]
        fill = sweep(asks, 6, D("1.47"), D(".01"))
        self.assertEqual(fill.levels, (Level(D(".22"), 3), Level(D(".38"), 2)))
        self.assertEqual(fill.principal, D("1.42"))
        self.assertEqual(fill.fees, D(".05"))
        self.assertEqual(fill.debit, D("1.47"))
        self.assertEqual(asks[0].price, D(".38"))

    def test_limit_price_and_no_liquidity(self):
        fill = sweep([Level(D(".24"), 3), Level(D(".25"), 20)],
                     10, D("100"), limit_price=D(".24"))
        self.assertEqual(fill.quantity, 3)
        self.assertEqual(sweep([], 10, D("8")).quantity, 0)

    def test_zero_cent_levels_still_need_cash_for_fees(self):
        asks = [Level(D("0"), 2)]
        self.assertEqual(sweep(asks, 2, D("0")).quantity, 2)
        self.assertEqual(sweep(asks, 2, D("0"), D(".01")).quantity, 0)

    def test_tiny_observed_fee_cannot_disappear_at_a_budget_boundary(self):
        with localcontext() as caller:
            caller.prec = 2
            asks = [Level(D(".5"), 2)]
            fill = sweep(asks, 2, D("1"), D("1e-29"))
            self.assertEqual(fill.quantity, 1)
            self.assertEqual(fill.debit, D(".50000000000000000000000000001"))
            plan = plan_pair(asks, asks, 2, D("3"), D("1e-29"), D("1"))
            self.assertEqual(plan.quantity, 0)
            self.assertEqual(caller.prec, 2)

    def test_large_budget_small_price_and_declared_limits(self):
        asks = [Level(D(".2"), 3)]
        self.assertEqual(sweep(asks, 3, D("1e30")).quantity, 3)
        self.assertEqual(sweep([Level(D("1e-30"), 1)], 1, D("1e36")).quantity, 1)
        for cash, fee in [(D("1e37"), D("0")), (D("1"), D("1e-31"))]:
            with self.subTest(cash=cash, fee=fee), self.assertRaisesRegex(ValueError, "supported"):
                sweep(asks, 3, cash, fee)
        with self.assertRaises(ValueError):
            sweep(asks, 10**18 + 1, D("2"))

    def test_invalid_inputs(self):
        for price, qty in [(D("NaN"), 1), (D("-.1"), 2), (D("1.001"), 2),
                           (0.5, 1), (D(".4"), 0), (D(".4"), True)]:
            with self.subTest(price=price, qty=qty), self.assertRaises(ValueError):
                Level(price, qty)
        for qty, cash, fee in [(-1, D("8"), D("0")), (1, D("-1"), D("0")),
                               (True, D("8"), D("0")), (1, D("8"), D("-.01"))]:
            with self.subTest(qty=qty, cash=cash, fee=fee), self.assertRaises(ValueError):
                sweep([], qty, cash, fee)


class PairTests(unittest.TestCase):
    def setUp(self):
        self.yes = [Level(D(".22"), 3), Level(D(".38"), 3)]
        self.no = [Level(D(".56"), 2), Level(D(".58"), 5)]
        self.fee = D(".01")

    def test_one_wallet_does_not_double_count_cash(self):
        plan = plan_pair(self.yes, self.no, 6, D("4.40"), self.fee)
        self.assertEqual(plan.quantity, 5)
        self.assertEqual(plan.no.quantity, 5)
        self.assertEqual(plan.yes.debit, D("1.47"))
        self.assertEqual(plan.no.debit, D("2.91"))
        self.assertEqual(plan.debit, D("4.38"))
        payout = settlement(plan.yes, plan.no)
        self.assertEqual((payout.pnl_if_yes, payout.pnl_if_no), (D(".62"), D(".62")))

    def test_marginal_cost_gate_rejects_more_expensive_tier(self):
        plan = plan_pair(self.yes, self.no, 20, D("100"), self.fee, D(".82"))
        self.assertEqual(plan.quantity, 3)
        self.assertEqual(plan.debit, D("2.42"))

    def test_second_snapshot_leaves_first_leg_exposed(self):
        cash = D("4.40")
        plan = plan_pair(self.yes, self.no, 6, cash, self.fee)
        first = sweep(self.yes, plan.quantity, cash, self.fee)
        changed_no = [Level(D(".58"), 2), Level(D(".80"), 20)]
        second = sweep(changed_no, first.quantity, cash - first.debit,
                       self.fee, limit_price=D(".58"))
        result = settlement(first, second)
        self.assertEqual(result.matched_quantity, 2)
        self.assertEqual((result.yes_unmatched, result.no_unmatched), (3, 0))
        self.assertEqual((result.pnl_if_yes, result.pnl_if_no), (D("2.35"), D("-.65")))

    def test_empty_side_has_no_pair_even_if_other_side_is_free(self):
        plan = plan_pair([Level(D("0"), 2)], [], 2, D("0"))
        self.assertEqual((plan.quantity, plan.debit), (0, D("0")))

    def test_matches_independent_share_by_share_oracle(self):
        # Includes every boundary within the small fixture, both fee cases
        # and offsets between the yes and no price tier sizes.
        yes = [D(".22")] * 3 + [D(".38")] * 3
        no = [D(".56")] * 2 + [D(".58")] * 5
        for budget, cap, fee, target in product(
            [D(i) / 10 for i in range(61)], [D(".8"), D(".82"), D("1")],
            [D("0"), D(".01")], [0, 1, 2, 3, 6, 7]
        ):
            cash, qty = budget, 0
            for y, n in list(zip(yes, no))[:target]:
                price = y + n + 2 * fee
                if price > cap or price > cash:
                    break
                cash -= price
                qty += 1
            plan = plan_pair(self.yes, self.no, target, budget, fee, cap)
            self.assertEqual((plan.quantity, plan.debit), (qty, budget - cash))


if __name__ == "__main__":
    unittest.main()
