import copy
import unittest

import support
from justification.justify import build_justification, render_text, verify
from risk_scoring.risk import thread_contributions, update_store
from risk_scoring.severity import attach


def make_store(*pairs):
    store = {"users": {}}
    for thread, classifier in pairs:
        capture = support.load(thread)
        update_store(store, capture["post_id"], thread_contributions(capture, attach(capture, support.load(classifier))))
    return store


class JustificationTests(unittest.TestCase):
    def setUp(self):
        self.store = make_store(("synthetic_thread.json", "synthetic_classifier.json"),
                                ("synthetic_thread_2.json", "synthetic_classifier_2.json"))

    def test_the_arithmetic_checks_out(self):
        for user in self.store["users"]:
            with self.subTest(user=user):
                verify(build_justification(self.store, user))

    def test_verify_catches_a_wrong_risk(self):
        j = build_justification(self.store, "u_syn_a")
        j["risk"] += 1
        with self.assertRaises(AssertionError):
            verify(j)

    def test_verify_catches_a_wrong_contribution(self):
        j = build_justification(self.store, "u_syn_a")
        j["posts"][0]["contribution"] += 0.5
        j["risk"] = round(sum(p["contribution"] for p in j["posts"]), 3)  # sums still agree
        with self.assertRaises(AssertionError):
            verify(j)

    def test_verify_catches_evidence_that_does_not_add_up(self):
        j = build_justification(self.store, "u_syn_a")
        j["posts"][0]["evidence"][0]["severity"] += 0.3
        with self.assertRaises(AssertionError):
            verify(j)

    def test_text_quotes_the_stored_numbers(self):
        text = render_text(build_justification(self.store, "u_syn_a"))
        for expected in ("FLAG", "risk 5.28", "flag threshold 3.0", "high severity report at 6.0",
                         "2.64 x (1 + 1.0) = 5.28", "comment 9000001", "political x2", "racial_ethnic x1"):
            with self.subTest(expected):
                self.assertIn(expected, text)
        self.assertIn("recommendation only", text)

    def test_text_says_when_a_thread_was_too_small_for_influence(self):
        text = render_text(build_justification(self.store, "u_syn_h"))
        self.assertIn("too small to measure influence", text)

    def test_a_user_below_every_tier_is_described_as_such(self):
        text = render_text(build_justification(self.store, "u_syn_b"))  # 0.72
        self.assertIn("no tier reached", text)

    def test_older_store_entries_without_evidence_still_render(self):
        for rec in self.store["users"].values():
            for p in rec["posts"].values():
                p.pop("evidence")
        j = build_justification(self.store, "u_syn_a")
        verify(j)
        self.assertIn("details not stored", render_text(j))

    def test_posts_are_listed_biggest_contribution_first(self):
        j = build_justification(self.store, "u_syn_h")
        contributions = [p["contribution"] for p in j["posts"]]
        self.assertEqual(contributions, sorted(contributions, reverse=True))


if __name__ == "__main__":
    unittest.main()
