import random
import unittest
from decimal import Decimal as D

from marketlab.ledger import Fill, Ledger


class LedgerTests(unittest.TestCase):
    def test_fifo_partial_offset_with_fees(self):
        book = Ledger(100)
        book.apply(Fill("a", "rain", "YES", 4, D(".24"), D(".04")))
        book.apply(Fill("b", "rain", "YES", 2, D(".61"), D(".06")))
        book.apply(Fill("c", "rain", "NO", 5, D(".19"), D(".05")))
        self.assertEqual(book.cash, D("101.72"))
        self.assertEqual(book.realized_pnl, D("2.36"))
        self.assertEqual(book.remaining_cost, D(".64"))
        self.assertEqual(book.position("rain"), 1)
        self.assertEqual(book.lots("rain")[0].fill.fill_id, "b")
        self.assertEqual(book.total_fees, D(".15"))
        book.settle("rain", "NO")
        self.assertEqual(book.cash, D("101.72"))
        self.assertEqual(book.remaining_cost, 0)
        self.assertEqual(book.realized_pnl, D("1.72"))

    def test_flip_through_zero_then_redeem(self):
        book = Ledger(100)
        book.apply(Fill("a", "rain", "NO", 2, D(".30"), D(".01")))
        self.assertEqual(book.position("rain"), -2)
        book.apply(Fill("b", "rain", "YES", 5, D(".55"), D(".05")))
        self.assertEqual(book.position("rain"), 3)
        self.assertEqual(book.remaining_cost, D("1.68"))
        self.assertEqual(book.realized_pnl, D(".27"))
        book.settle("rain", "YES")
        self.assertEqual(book.cash, D("101.59"))
        self.assertEqual(book.realized_pnl, D("1.59"))

    def test_replay_before_and_after_settlement_and_conflict(self):
        book = Ledger(5)
        fill = Fill("a", "rain", "YES", 2, D(".50"))
        self.assertTrue(book.apply(fill))
        self.assertFalse(book.apply(fill))
        with self.assertRaisesRegex(ValueError, "conflicting event"):
            book.apply(Fill("a", "sun", "YES", 2, D(".50")))
        self.assertTrue(book.settle("rain", "YES"))
        self.assertFalse(book.settle("rain", "YES"))
        self.assertFalse(book.apply(fill))
        with self.assertRaisesRegex(ValueError, "conflicting settlement"):
            book.settle("rain", "NO")
        with self.assertRaisesRegex(ValueError, "settled"):
            book.apply(Fill("b", "rain", "YES", 2, D(".50")))
        self.assertEqual(book.cash, D("6"))
        self.assertEqual(book.realized_pnl, D("1"))

    def test_rejected_prefunding_is_atomic_and_does_not_consume_id(self):
        book = Ledger(1)
        book.apply(Fill("a", "rain", "NO", 1, D(".9")))
        with self.assertRaisesRegex(ValueError, "insufficient"):
            book.apply(Fill("b", "rain", "YES", 1, D(".2")))
        self.assertEqual(book.cash, D(".1"))
        self.assertEqual(book.position("rain"), -1)
        self.assertEqual(book.realized_pnl, 0)
        self.assertTrue(book.apply(Fill("b", "rain", "YES", 1, D(".1"))))
        self.assertEqual(book.cash, 1)

    def test_indivisible_fee_conserved_across_partial_closes(self):
        book = Ledger(10)
        book.apply(Fill("a", "rain", "YES", 3, D(".1"), D(".000001")))
        for index in range(2):
            book.apply(Fill(str(index), "rain", "NO", 1, D(".3")))
        self.assertEqual(book.remaining_cost, D(".100001"))
        self.assertEqual(book.realized_pnl, D("1.2"))
        book.settle("rain", "NO")
        self.assertEqual(book.cash, D("11.099999"))
        self.assertEqual(book.realized_pnl, D("1.099999"))

    def test_invalid_values(self):
        for price in (D("NaN"), D("Infinity"), D("-.1"), D("1.2"),
                      D(".0000001"), 0.1):
            with self.subTest(price=price), self.assertRaises(ValueError):
                Fill("a", "rain", "YES", 2, price)
        for qty in (True, 0, -1, D("1")):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                Fill("a", "rain", "YES", qty, D(".2"))
        with self.assertRaises(ValueError):
            Fill("a", "rain", "NO", 1, D(".3"), D("-.1"))
        with self.assertRaises(ValueError):
            Ledger(-1)

    def test_cash_identity_after_each_fill_and_settlement(self):
        book = Ledger(1000)
        rng = random.Random(17)
        for index in range(200):
            market = rng.choice(("sun", "wind", "rain"))
            side = rng.choice(("YES", "NO"))
            count = rng.randint(1, 10)
            price = D(rng.randint(0, 100)) / 100
            fee = D(rng.randint(0, 7)) / 100
            book.apply(Fill(str(index), market, side, count, price, fee))
            self.assertEqual(book.cash + book.remaining_cost,
                             book.initial_cash + book.realized_pnl)
        for market, winner in (("sun", "NO"), ("wind", "YES"), ("rain", "NO")):
            book.settle(market, winner)
        self.assertEqual(book.remaining_cost, 0)
        self.assertEqual(book.cash, book.initial_cash + book.realized_pnl)


if __name__ == "__main__":
    unittest.main()
