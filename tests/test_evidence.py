import unittest
from decimal import Decimal as D

from marketlab.evidence import Report, report_as_of


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.first = Report("measure passes", 25, 0, 28, D(".56"))
        self.revision = Report("measure passes", 25, 1, 44, D(".40"))
        self.repeat = Report("measure passes", 25, 0, 37, D(".56"))
        self.other = Report("measure takes effect", 30, 0, 31, D(".83"))
        self.stream = [self.revision, self.repeat, self.other, self.first]

    def test_late_revision_cannot_change_earlier_decision(self):
        self.assertEqual(report_as_of(self.stream, "measure passes", 40, 30), self.first)
        self.assertEqual(report_as_of(self.stream, "measure passes", 44, 30), self.revision)

    def test_new_receipt_of_old_information_does_not_refresh_age(self):
        self.assertIsNone(report_as_of(self.stream, "measure passes", 45, 19))
        self.assertEqual(report_as_of(self.stream, "measure passes", 45, 20), self.revision)

    def test_different_terms_and_future_receipts_excluded(self):
        self.assertIsNone(report_as_of(self.stream, "measure passes", 26, 30))
        self.assertIsNone(report_as_of(self.stream, "different terms", 44, 60))

    def test_conflicting_version_only_becomes_ambiguous_on_receipt(self):
        conflict = Report("measure passes", 25, 0, 41, D(".80"))
        stream = [self.first, conflict]
        self.assertEqual(report_as_of(stream, "measure passes", 40, 30), self.first)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            report_as_of(stream, "measure passes", 41, 30)
