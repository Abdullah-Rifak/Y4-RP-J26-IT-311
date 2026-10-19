import copy
import unittest

import support
from risk_scoring.risk import thread_contributions, update_store, user_risk
from risk_scoring.severity import attach


def contributions(thread_file, classifier_file, mutate=None):
    capture = support.load(thread_file)
    records = support.load(classifier_file)
    if mutate:
        mutate(records)
    return capture, thread_contributions(capture, attach(capture, records))


class ContributionTests(unittest.TestCase):
    def setUp(self):
        _, self.c = contributions("synthetic_thread.json", "synthetic_classifier.json")

    def test_influential_user_is_weighted_up(self):
        a = self.c["u_syn_a"]  # most replied-to, and the bridge, in this thread
        self.assertEqual(a["influence"], 1.0)
        self.assertEqual(a["contribution"], round(2.64 * 2, 3))  # 5.28

    def test_user_nobody_replied_to_is_not_weighted_up(self):
        h = self.c["u_syn_h"]
        self.assertEqual(h["influence"], 0.0)
        self.assertEqual(h["contribution"], 2.34)

    def test_only_flagged_users_are_stored(self):
        self.assertNotIn("u_syn_g", self.c)  # one not_hate and one unclassified comment
        self.assertNotIn("u_syn_c", self.c)
        self.assertEqual(set(self.c), {"u_syn_a", "u_syn_b", "u_syn_d", "u_syn_f", "u_syn_h"})

    def test_evidence_lists_flagged_comments_strongest_first(self):
        ev = self.c["u_syn_a"]["evidence"]
        self.assertEqual([e["comment_id"] for e in ev], ["9000001", "9000005", "9000008"])
        self.assertEqual(round(sum(e["severity"] for e in ev), 3), self.c["u_syn_a"]["total_severity"])

    def test_small_thread_counts_severity_but_not_influence(self):
        _, small = contributions("synthetic_thread_2.json", "synthetic_classifier_2.json")
        h = small["u_syn_h"]
        self.assertFalse(h["centrality_applied"])
        self.assertEqual(h["influence"], 0.0)
        self.assertEqual(h["contribution"], h["total_severity"])


class StoreTests(unittest.TestCase):
    def ingest(self, store, thread, classifier, mutate=None):
        capture, c = contributions(thread, classifier, mutate)
        update_store(store, capture["post_id"], c)

    def test_recapturing_the_same_post_does_not_double_count(self):
        store = {"users": {}}
        self.ingest(store, "synthetic_thread.json", "synthetic_classifier.json")
        first = {u: user_risk(store, u) for u in store["users"]}
        self.ingest(store, "synthetic_thread.json", "synthetic_classifier.json")
        self.assertEqual({u: user_risk(store, u) for u in store["users"]}, first)

    def test_risk_accumulates_across_posts(self):
        store = {"users": {}}
        self.ingest(store, "synthetic_thread.json", "synthetic_classifier.json")
        self.assertEqual(user_risk(store, "u_syn_h"), 2.34)
        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json")
        self.assertEqual(user_risk(store, "u_syn_h"), round(2.34 + 0.55 + 0.53 + 0.56, 3))  # 3.98

    def test_risk_never_goes_down_when_more_offences_arrive(self):
        store = {"users": {}}
        self.ingest(store, "synthetic_thread.json", "synthetic_classifier.json")
        before = user_risk(store, "u_syn_h")
        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json")
        self.assertGreater(user_risk(store, "u_syn_h"), before)

    def test_a_changed_recapture_replaces_instead_of_adding(self):
        store = {"users": {}}
        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json")
        old = user_risk(store, "u_syn_h")

        def stronger(records):
            for r in records[:3]:
                r["confidence_score"] = 0.9

        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json", stronger)
        self.assertEqual(user_risk(store, "u_syn_h"), round(0.9 * 3, 3))
        self.assertGreater(user_risk(store, "u_syn_h"), old)

    def test_a_user_with_no_flagged_comments_left_is_dropped(self):
        store = {"users": {}}
        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json")
        self.assertIn("u_syn_h", store["users"])

        def all_clear(records):
            for r in records:
                r["predicted_category"] = "not_hate"

        self.ingest(store, "synthetic_thread_2.json", "synthetic_classifier_2.json", all_clear)
        self.assertNotIn("u_syn_h", store["users"])


if __name__ == "__main__":
    unittest.main()
