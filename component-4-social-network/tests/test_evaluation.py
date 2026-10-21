import unittest

import support
from evaluation import benchmark
from evaluation.baselines import detection_only, proposed, volume_based
from evaluation.metrics import is_monotonic, ranking, spearman, tier_report, top_k_overlap

TIERS = ["none", "warning", "flag", "high_severity_report"]


class SpearmanTests(unittest.TestCase):
    def test_identical_and_reversed_rankings(self):
        self.assertAlmostEqual(spearman({"a": 1, "b": 2, "c": 3}, {"a": 10, "b": 20, "c": 30}), 1.0)
        self.assertAlmostEqual(spearman({"a": 1, "b": 2, "c": 3}, {"a": 3, "b": 2, "c": 1}), -1.0)

    def test_hand_calculated_values(self):
        self.assertAlmostEqual(spearman({"a": 1, "b": 2, "c": 3}, {"a": 1, "b": 3, "c": 2}), 0.5)
        # ties share an average rank: ranks 1, 2.5, 2.5, 4 against 1, 2, 3, 4
        self.assertAlmostEqual(
            spearman({"a": 1, "b": 2, "c": 2, "d": 3}, {"a": 1, "b": 2, "c": 3, "d": 4}), 4.5 / (4.5 * 5) ** 0.5)

    def test_a_user_missing_from_one_side_counts_as_zero(self):
        self.assertAlmostEqual(spearman({"a": 5, "b": 3}, {"a": 5, "b": 3, "c": 0}), 1.0)

    def test_undefined_cases_return_none(self):
        self.assertIsNone(spearman({"a": 1}, {"a": 1}))  # one user
        self.assertIsNone(spearman({"a": 1, "b": 1}, {"a": 1, "b": 2}))  # no variation on one side


class RankingTests(unittest.TestCase):
    def test_ranking_and_ties_are_stable(self):
        self.assertEqual(ranking({"b": 1, "a": 1, "c": 2}), ["c", "a", "b"])

    def test_top_k_overlap(self):
        a, b = {"x": 3, "y": 2, "z": 1}, {"x": 1, "y": 3, "z": 2}
        self.assertEqual(top_k_overlap(a, b, 1), 0.0)
        self.assertAlmostEqual(top_k_overlap(a, b, 2), 0.5)
        self.assertEqual(top_k_overlap(a, b, 3), 1.0)


class TierReportTests(unittest.TestCase):
    def test_agreement_precision_recall_and_confusion(self):
        expected = {"a": "flag", "b": "warning", "c": "none", "d": "flag"}
        predicted = {"a": "flag", "b": "flag", "c": "none", "d": "warning"}
        r = tier_report(predicted, expected, TIERS)
        self.assertEqual(r["n"], 4)
        self.assertEqual(r["agreement"], 0.5)
        self.assertEqual((r["per_tier"]["flag"]["precision"], r["per_tier"]["flag"]["recall"]), (0.5, 0.5))
        self.assertEqual((r["per_tier"]["warning"]["precision"], r["per_tier"]["warning"]["recall"]), (0.0, 0.0))
        self.assertEqual((r["per_tier"]["none"]["precision"], r["per_tier"]["none"]["recall"]), (1.0, 1.0))
        self.assertIsNone(r["per_tier"]["high_severity_report"]["precision"])  # never predicted
        self.assertEqual(r["confusion"]["flag"], {"none": 0, "warning": 1, "flag": 1, "high_severity_report": 0})

    def test_precision_and_recall_use_different_denominators(self):
        # the system flags 1 user (correctly) but the experts wanted 3 flagged
        expected = {"a": "flag", "b": "flag", "c": "flag"}
        predicted = {"a": "flag", "b": "none", "c": "none"}
        flag = tier_report(predicted, expected, TIERS)["per_tier"]["flag"]
        self.assertEqual(flag["precision"], 1.0)  # 1 correct of 1 predicted
        self.assertAlmostEqual(flag["recall"], 1 / 3)  # 1 found of 3 expected
        self.assertEqual(flag["support"], 3)

    def test_user_missing_from_predictions_counts_as_none(self):
        r = tier_report({}, {"a": "none", "b": "flag"}, TIERS)
        self.assertEqual(r["agreement"], 0.5)


class MonotonicTests(unittest.TestCase):
    def test_monotonic(self):
        self.assertTrue(is_monotonic([1, 1, 2, 3.5]))
        self.assertFalse(is_monotonic([1, 2, 1.9]))
        self.assertTrue(is_monotonic([]))


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.p1 = (support.load("synthetic_thread.json"), support.load("synthetic_classifier.json"))
        self.p2 = (support.load("synthetic_thread_2.json"), support.load("synthetic_classifier_2.json"))

    def test_detection_only_uses_one_post_and_the_highest_severity(self):
        a = detection_only(*self.p1)
        self.assertEqual(a["u_syn_a"], 0.9)
        self.assertEqual(a["u_syn_h"], 0.7)
        self.assertNotIn("u_syn_g", a)

    def test_volume_counts_flagged_comments_across_posts(self):
        self.assertEqual(volume_based([self.p1])["u_syn_h"], 4)
        self.assertEqual(volume_based([self.p1])["u_syn_a"], 3)
        self.assertEqual(volume_based([self.p1, self.p2])["u_syn_h"], 7)

    def test_the_methods_disagree_on_who_is_first(self):
        self.assertEqual(ranking(volume_based([self.p1]))[0], "u_syn_h")  # most comments
        self.assertEqual(ranking(proposed([self.p1]))[0], "u_syn_a")  # strongest and most influential

    def test_proposed_matches_the_scores_seen_elsewhere(self):
        p = proposed([self.p1, self.p2])
        self.assertEqual(p["u_syn_a"], 5.28)
        self.assertEqual(p["u_syn_h"], 3.98)

    def test_proposed_never_lowers_a_users_risk_as_posts_are_added(self):
        series = [proposed(posts).get("u_syn_h", 0.0) for posts in ([], [self.p1], [self.p1, self.p2])]
        self.assertTrue(is_monotonic(series))
        self.assertEqual(series, [0.0, 2.34, 3.98])


class BenchmarkTests(unittest.TestCase):
    def test_thread_generator_is_reproducible_and_the_right_size(self):
        c1, r1 = benchmark.make_thread(100, 30, seed=7)
        c2, r2 = benchmark.make_thread(100, 30, seed=7)
        self.assertEqual((c1, r1), (c2, r2))
        self.assertEqual(len(c1["comments"]), 100)
        self.assertEqual(len(r1), 100)
        self.assertNotEqual(c1, benchmark.make_thread(100, 30, seed=8)[0])

    def test_pipeline_runs_on_a_generated_thread(self):
        capture, records = benchmark.make_thread(60, 15)
        benchmark.run_once(capture, records)  # must not raise


if __name__ == "__main__":
    unittest.main()
