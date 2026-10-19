import unittest
from unittest import mock

import support
from risk_scoring import config
from risk_scoring.severity import attach, severity, user_summary, validate


def rec(cid, cat, conf, comp="sinhala-english"):
    return dict(comment_id=cid, source_component=comp, predicted_category=cat, confidence_score=conf)


class SeverityTests(unittest.TestCase):
    def test_not_hate_is_zero(self):
        self.assertEqual(severity("not_hate", 0.99), 0.0)

    def test_below_the_confidence_floor_is_zero(self):
        self.assertEqual(severity("political", config.CONFIDENCE_FLOOR - 0.01), 0.0)

    def test_at_the_floor_counts(self):
        self.assertEqual(severity("political", config.CONFIDENCE_FLOOR), config.CONFIDENCE_FLOOR)

    def test_severity_is_confidence_times_weight(self):
        self.assertEqual(severity("political", 0.9), 0.9)  # weights are all 1.0 for now
        with mock.patch.dict(config.CATEGORY_WEIGHTS, {"political": 2.0}):
            self.assertEqual(severity("political", 0.9), 1.8)


class ValidationTests(unittest.TestCase):
    def test_good_records_pass(self):
        validate([rec("1", "political", 0.8), rec("2", "not_hate", 0.9)])

    def test_missing_field_unknown_category_and_bad_confidence_are_all_reported(self):
        bad = [{"comment_id": "1"}, rec("2", "banana", 0.5), rec("3", "political", 1.5)]
        with self.assertRaises(ValueError) as ctx:
            validate(bad)
        msg = str(ctx.exception)
        self.assertIn("missing", msg)
        self.assertIn("unknown category", msg)
        self.assertIn("not in [0, 1]", msg)


class AttachTests(unittest.TestCase):
    def setUp(self):
        self.capture = support.load("synthetic_thread.json")
        self.scored = {s["comment_id"]: s for s in attach(self.capture, support.load("synthetic_classifier.json"))}

    def test_every_comment_is_present(self):
        self.assertEqual(len(self.scored), 16)

    def test_two_records_for_one_comment_keep_the_highest_severity(self):
        s = self.scored["9000010"]  # text 0.55 and meme 0.70
        self.assertEqual(s["severity"], 0.7)
        self.assertEqual(s["source"], "meme")

    def test_a_comment_with_no_record_is_unclassified_not_zero(self):
        s = self.scored["9000014"]
        self.assertIsNone(s["severity"])
        self.assertNotEqual(s["severity"], 0)

    def test_user_summary_totals(self):
        users = {u["user"]: u for u in user_summary(list(self.scored.values()))}
        self.assertEqual(users["u_syn_a"]["total"], 2.64)  # 0.90 + 0.88 + 0.86
        self.assertEqual(users["u_syn_h"]["total"], 2.34)  # 0.70 + 0.52 + 0.58 + 0.54
        self.assertEqual(users["u_syn_h"]["flagged"], 4)
        self.assertEqual(users["u_syn_g"]["unclassified"], 1)
        self.assertEqual(users["u_syn_c"]["flagged"], 0)


if __name__ == "__main__":
    unittest.main()
