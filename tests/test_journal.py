import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from marketlab.journal import IntentJournal


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
