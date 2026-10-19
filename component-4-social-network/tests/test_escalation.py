import tempfile
import unittest
from pathlib import Path

import support  # noqa: F401
from escalation import review
from escalation.tiers import TIERS, next_tier, recommended_tier


class TierTests(unittest.TestCase):
    def test_boundaries(self):
        cases = [(0, "none"), (0.99, "none"), (1.0, "warning"), (2.99, "warning"),
                 (3.0, "flag"), (5.99, "flag"), (6.0, "high_severity_report"), (50, "high_severity_report")]
        for risk, expected in cases:
            with self.subTest(risk=risk):
                self.assertEqual(recommended_tier(risk), expected)

    def test_tier_order_is_lowest_to_highest(self):
        self.assertEqual(TIERS, ["none", "warning", "flag", "high_severity_report"])

    def test_next_tier(self):
        self.assertEqual(next_tier(0), ("warning", 1.0))
        self.assertEqual(next_tier(3.0), ("high_severity_report", 6.0))
        self.assertIsNone(next_tier(6.0))


class DecisionRuleTests(unittest.TestCase):
    RISK = 5.28  # recommends "flag"

    def decide(self, **kw):
        args = dict(user="u1", risk=self.RISK, decision="accept", reviewer="m1", note="", final_tier=None)
        args.update(kw)
        return review.make_decision(**args)

    def test_accept_records_the_recommended_tier(self):
        e = self.decide()
        self.assertEqual((e["recommended_tier"], e["final_tier"], e["decision"]), ("flag", "flag", "accept"))
        self.assertEqual(e["risk"], self.RISK)

    def test_override_with_a_reason_is_recorded(self):
        e = self.decide(decision="override", final_tier="warning", note="  context was banter  ")
        self.assertEqual((e["final_tier"], e["note"]), ("warning", "context was banter"))

    def test_override_to_none_is_a_dismissal(self):
        self.assertEqual(self.decide(decision="override", final_tier="none", note="fine")["final_tier"], "none")

    def test_rejected_decisions(self):
        bad = {
            "no reviewer": dict(reviewer="   "),
            "override without a reason": dict(decision="override", final_tier="none", note=" "),
            "override to the same tier": dict(decision="override", final_tier="flag", note="x"),
            "override to an unknown tier": dict(decision="override", final_tier="ban", note="x"),
            "override with no tier": dict(decision="override", note="x"),
            "unknown decision type": dict(decision="approve"),
        }
        for label, kw in bad.items():
            with self.subTest(label):
                with self.assertRaises(ValueError):
                    self.decide(**kw)


class ReviewLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "log.jsonl"

    def add(self, user, risk, reviewer="m1"):
        review.append_decision(review.make_decision(user, risk, "accept", reviewer), self.log)

    def test_make_decision_writes_nothing(self):
        review.make_decision("u1", 5.0, "accept", "m1")
        self.assertFalse(self.log.exists())

    def test_log_is_append_only_and_per_user(self):
        self.add("u1", 5.0)
        self.add("u2", 2.0)
        self.add("u1", 5.0, reviewer="m2")
        self.assertEqual(len(review.read_log(self.log)), 3)
        self.assertEqual([d["reviewer"] for d in review.decisions_for("u1", self.log)], ["m1", "m2"])

    def test_review_status(self):
        self.assertEqual(review.review_status("u1", 5.0, self.log), "pending")
        self.add("u1", 5.0)
        self.assertEqual(review.review_status("u1", 5.0, self.log), "reviewed")
        self.assertEqual(review.review_status("u1", 5.01, self.log), "changed_since_review")

    def test_missing_log_reads_as_empty(self):
        self.assertEqual(review.read_log(self.log), [])


if __name__ == "__main__":
    unittest.main()
