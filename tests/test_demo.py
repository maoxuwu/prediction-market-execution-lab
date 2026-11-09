import unittest
from decimal import Decimal as D

from marketlab.demo import run


class DemoTests(unittest.TestCase):
    def test_partial_second_leg(self):
        r = run(2)
        self.assertEqual(r["planned pairs"], 5)
        self.assertEqual(r["planned all-in cost"], D("4.48"))
        self.assertEqual(r["cash after offsets"] + r["open FIFO cost"],
                         12 + r["realised P&L"])
        self.assertEqual(r["terminal P&L if YES"], D("2.11"))
        self.assertEqual(r["terminal P&L if NO"], D("-.89"))

    def test_fill_extremes(self):
        empty = run(0)
        self.assertEqual(empty["open YES shares"], 5)
        self.assertEqual(empty["terminal P&L if NO"], D("-1.85"))
        complete = run(5)
        self.assertEqual(complete["open YES shares"], 0)
        self.assertEqual(complete["terminal P&L if YES"], complete["realised P&L"])
        self.assertEqual(complete["terminal P&L if NO"], complete["realised P&L"])
