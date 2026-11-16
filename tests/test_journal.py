from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import replace
import sqlite3
from threading import Barrier
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from marketlab.journal import Balance, Buy, History, IntentJournal, OrderRecord, Trade


class JournalTests(unittest.TestCase):
    def test_restart_after_ambiguous_send(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "journal.db"
            with IntentJournal(path) as sender:
                self.assertTrue(sender.claim("attempt-A", "buy 4 YES"))
            with IntentJournal(path) as recovered, IntentJournal(path) as second:
                self.assertEqual(recovered.unresolved(), ("attempt-A",))
                self.assertFalse(second.claim("attempt-A", "buy 4 YES"))
                with self.assertRaises(ValueError):
                    recovered.claim("attempt-A", "buy 8 YES")
                recovered.confirm("attempt-A", "terminal-partial-fill")
                second.confirm("attempt-A", "terminal-partial-fill")
                self.assertFalse(second.claim("attempt-A", "buy 4 YES"))
                self.assertEqual(second.unresolved(), ())

    def test_terminal_evidence_has_one_owner(self):
        with TemporaryDirectory() as tmp, IntentJournal(Path(tmp) / "j.db") as journal:
            journal.claim("A", "first")
            journal.claim("B", "second")
            journal.confirm("A", "receipt-1")
            with self.assertRaises(sqlite3.IntegrityError):
                journal.confirm("B", "receipt-1")
            with self.assertRaises(ValueError):
                journal.confirm("A", "receipt-2")
            with self.assertRaises(ValueError):
                journal.confirm("C", "receipt-3")
            self.assertEqual(journal.unresolved(), ("B",))

    def test_malformed_proof_cannot_resolve_pending_intent(self):
        with TemporaryDirectory() as tmp, IntentJournal(Path(tmp) / "j.db") as journal:
            with self.assertRaises(ValueError):
                journal.claim("   ", "payload")
            journal.claim("A", "buy")
            for receipt in (" ", 12, None):
                with self.assertRaises(ValueError):
                    journal.confirm("A", receipt)
            self.assertEqual(journal.unresolved(), ("A",))


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "test.db"
        self.buy = Buy("wallet", "kite", "NO", 7, 41, 90)
        self.opening = Balance(20, 780, 1)
        self.history = History("statement", "wallet", "kite", "NO", 20,
                               Balance(91, 780, 1), True, (), ())
        self.order = OrderRecord("venue-8", self.buy, 31, True, 3)
        self.fill = Trade("fill-1", "venue-8", 38, 3, 36, 2)
        self.matched = replace(self.history, closing=Balance(91, 670, 4),
                               orders=(self.order,), trades=(self.fill,))

    def send(self):
        with IntentJournal(self.path) as journal:
            self.assertTrue(journal.prepare("local", self.buy, self.opening))
            self.assertTrue(journal.mark_maybe_sent("local", 30))

    def test_preparation_and_send_permission_survive_separate_restarts(self):
        with IntentJournal(self.path) as first:
            self.assertTrue(first.prepare("local", self.buy, self.opening))
        with IntentJournal(self.path) as second:
            self.assertFalse(second.prepare("local", self.buy, self.opening))
            self.assertEqual(second.status("local"), "PREPARED")
            for wrong in (replace(self.buy, quantity=2), replace(self.buy, market="other")):
                with self.assertRaises(ValueError):
                    second.prepare("local", wrong, self.opening)
            with self.assertRaises(ValueError):
                second.prepare("local", self.buy, replace(self.opening, shares=0))
            with self.assertRaises(ValueError):
                second.recover("local", self.history)
            self.assertFalse(second.mark_maybe_sent("local", 19))
            self.assertFalse(second.mark_maybe_sent("local", 90))
            self.assertTrue(second.mark_maybe_sent("local", 30))
        with IntentJournal(self.path) as third:
            self.assertFalse(third.mark_maybe_sent("local", 31))
            self.assertEqual(third.status("local"), "POSSIBLY_SENT")
            with self.assertRaises(ValueError):
                third.confirm("local", "unverified-ack")

    def test_unique_terminal_partial_fill_matches_cost_quantity_and_fees(self):
        self.send()
        with IntentJournal(self.path) as journal:
            self.assertEqual(journal.recover("local", self.matched), "MATCHED_ORDER")
            self.assertEqual(journal.unresolved(), ())
        with IntentJournal(self.path) as restarted:
            self.assertEqual(restarted.status("local"), "MATCHED_ORDER")
            self.assertEqual(restarted.recover("local", self.matched), "MATCHED_ORDER")
            self.assertFalse(restarted.mark_maybe_sent("local", 40))
            with self.assertRaises(ValueError):
                restarted.recover("local", self.history)

    def test_no_effect_requires_complete_post_expiry_window_and_unchanged_account(self):
        self.send()
        with IntentJournal(self.path) as journal:
            for evidence in (
                replace(self.history, starts_at=25), replace(self.history, complete=False),
                replace(self.history, wallet="elsewhere"), replace(self.history, market="other"),
                replace(self.history, side="YES"), replace(self.history, closing=Balance(90, 780, 1)),
                replace(self.history, closing=Balance(91, 778, 1)),
                replace(self.history, closing=Balance(91, 780, 2)),
                replace(self.history, trades=(self.fill,)), replace(self.history, orders=None),
                replace(self.history, trades=None), replace(self.history, orders={}),
                replace(self.history, trades=""), replace(self.history, closing=None),
                replace(self.history, orders=(None,)), replace(self.history, trades=(False,)),
            ):
                with self.subTest(evidence=evidence):
                    self.assertEqual(journal.recover("local", evidence), "POSSIBLY_SENT")
            self.assertEqual(journal.unresolved(), ("local",))
            self.assertEqual(journal.recover("local", self.history), "NO_EFFECT")
            self.assertEqual(journal.recover("local", self.history), "NO_EFFECT")

    def test_ambiguous_or_open_or_unreconciled_match_remains_pending(self):
        self.send()
        with IntentJournal(self.path) as journal:
            changed_orders = [
                (self.order, replace(self.order, order_id="venue-9")),
                (replace(self.order, terminal=False),), (replace(self.order, filled=4),),
                (replace(self.order, accepted_at=29),), (replace(self.order, accepted_at=91),),
            ]
            for field, new in (("quantity", 6), ("limit_cents", 40), ("side", "YES"),
                               ("wallet", "other"), ("market", "other"), ("expires_at", 89)):
                changed_orders.append((replace(self.order, request=replace(self.buy, **{field: new})),))
            for row in changed_orders:
                with self.subTest(orders=row):
                    evidence = replace(self.matched, orders=row)
                    self.assertEqual(journal.recover("local", evidence), "POSSIBLY_SENT")
            for evidence in (
                replace(self.matched, trades=()), replace(self.matched, trades=(self.fill, self.fill)),
                replace(self.matched, closing=Balance(91, 672, 4)),
                replace(self.matched, closing=Balance(91, 670, 3)),
                replace(self.matched, trades=(replace(self.fill, order_id="venue-9"),)),
                replace(self.matched, trades=(replace(self.fill, at=28),)),
                replace(self.matched, trades=(replace(self.fill, price_cents=42),)),
            ):
                self.assertEqual(journal.recover("local", evidence), "POSSIBLY_SENT")
            self.assertEqual(journal.status("local"), "POSSIBLY_SENT")

    def test_terminal_no_fill_order_is_still_a_matched_order(self):
        self.send()
        record = replace(self.order, filled=0)
        with IntentJournal(self.path) as journal:
            self.assertEqual(journal.recover("local", replace(self.history, orders=(record,))),
                             "MATCHED_ORDER")

    def test_one_wallet_cannot_start_two_attempts_concurrently(self):
        with IntentJournal(self.path) as journal:
            for intent in ("a", "b"):
                journal.prepare(intent, self.buy, self.opening)
        ready = Barrier(2)

        def try_send(intent):
            with IntentJournal(self.path) as journal:
                ready.wait(timeout=5)
                return journal.mark_maybe_sent(intent, 30)

        with ThreadPoolExecutor(max_workers=2) as threads:
            self.assertEqual(sorted(threads.map(try_send, ("a", "b"))), [False, True])

    def test_new_opaque_claim_waits_for_structured_buy_to_resolve(self):
        self.send()
        with IntentJournal(self.path) as journal:
            self.assertFalse(journal.claim("opaque", "another buy"))
            self.assertEqual(journal.unresolved(), ("local",))
            journal.recover("local", self.history)
            self.assertTrue(journal.claim("opaque", "another buy"))
            self.assertFalse(journal.claim("opaque", "another buy"))

    def test_original_database_without_recovery_table_opens_conservatively(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE intents(intent_id TEXT PRIMARY KEY NOT NULL, "
                       "payload TEXT NOT NULL, terminal_receipt TEXT UNIQUE)")
            db.execute("INSERT INTO intents VALUES ('old','something',NULL)")
        with IntentJournal(self.path) as journal:
            self.assertEqual(journal.status("old"), "POSSIBLY_SENT")
            self.assertFalse(journal.mark_maybe_sent("old", 30))
            with self.assertRaises(ValueError):
                journal.prepare("old", self.buy, self.opening)
            journal.prepare("new", self.buy, self.opening)
            self.assertFalse(journal.mark_maybe_sent("new", 30))
            journal.confirm("old", "externally-verified")
            self.assertTrue(journal.mark_maybe_sent("new", 30))

    def test_conflicting_match_leaves_second_intent_unresolved(self):
        self.send()
        with IntentJournal(self.path) as journal:
            journal.recover("local", self.matched)
            other = replace(self.buy, wallet="second-wallet")
            journal.prepare("second", other, self.opening)
            journal.mark_maybe_sent("second", 30)
            conflict = replace(self.matched, receipt="second-statement", wallet=other.wallet,
                               orders=(replace(self.order, request=other),))
            with self.assertRaises(sqlite3.IntegrityError):
                journal.recover("second", conflict)
            self.assertEqual(journal.status("second"), "POSSIBLY_SENT")
            self.assertEqual(journal.unresolved(), ("second",))
