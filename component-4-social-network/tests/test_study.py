import csv
import json
import re
import tempfile
import unittest
from pathlib import Path

import support
from evaluation import study, study_analysis as sa
from evaluation.stats import holm, min_possible_p, wilcoxon_exact

P1 = ("synthetic_thread.json", "synthetic_classifier.json")
P2 = ("synthetic_thread_2.json", "synthetic_classifier_2.json")


def scenario(sid, posts):
    return {"id": sid, "description": "d", "posts": [{"capture": t, "classifier": k} for t, k in posts], "expected": {}}


# s1 gives users a, b, d, f, h (post 1 only); s2 gives h with two posts of history; s3 gives h again on post 2 only
DOC = {"scenarios": [scenario("s1", [P1]), scenario("s2", [P1, P2]), scenario("s3", [P2])]}


class WilcoxonTests(unittest.TestCase):
    def test_all_positive_differences(self):
        self.assertAlmostEqual(wilcoxon_exact([1, 2, 3, 4, 5])["p"], 2 / 32)
        self.assertAlmostEqual(wilcoxon_exact([1, 2, 3, 4, 5, 6])["p"], 2 / 64)

    def test_mixed_signs_hand_counted(self):
        # ranks 1..6, positives 1,3,4,6 -> W+ = 14, W- = 7; 18 of 64 sign patterns sum to 7 or less
        r = wilcoxon_exact([1, -2, 3, 4, -5, 6])
        self.assertEqual(r["w_plus"], 14)
        self.assertAlmostEqual(r["p"], 36 / 64)

    def test_zero_differences_are_dropped(self):
        self.assertEqual(wilcoxon_exact([0, 0, 1, 2, 3]), wilcoxon_exact([1, 2, 3]))
        self.assertAlmostEqual(wilcoxon_exact([0, 1, 2, 3])["p"], 2 / 8)

    def test_ties_share_average_ranks(self):
        self.assertAlmostEqual(wilcoxon_exact([1, 1, 2])["p"], 0.25)  # ranks 1.5, 1.5, 3, all positive
        self.assertAlmostEqual(wilcoxon_exact([1, -1, 2])["p"], 0.75)  # W+ = 4.5

    def test_ranks_follow_the_size_of_the_difference_not_its_position(self):
        # |3|, |1|, |2| rank 3, 1, 2 -> W+ = 3 + 2 = 5; patterns of {1,2,3} summing to 5 or more: 2 of 8
        r = wilcoxon_exact([3, -1, 2])
        self.assertEqual(r["w_plus"], 5)
        self.assertAlmostEqual(r["p"], 2 * 2 / 8)

    def test_no_usable_differences(self):
        r = wilcoxon_exact([0, 0])
        self.assertEqual((r["n"], r["p"]), (0, None))

    def test_the_sign_does_not_change_the_p_value(self):
        self.assertAlmostEqual(wilcoxon_exact([1, 2, 3, 4, 5])["p"], wilcoxon_exact([-1, -2, -3, -4, -5])["p"])

    def test_smallest_possible_p(self):
        self.assertEqual(min_possible_p(5), 2 / 32)  # 0.0625: can never reach 0.05
        self.assertAlmostEqual(min_possible_p(6), 2 / 64)
        self.assertEqual(min_possible_p(0), 1.0)
        self.assertEqual(min_possible_p(1), 1.0)


class HolmTests(unittest.TestCase):
    def test_adjustment(self):
        self.assertEqual([round(x, 3) for x in holm([0.01, 0.04, 0.03])], [0.03, 0.06, 0.06])

    def test_none_is_kept_and_values_are_capped_at_one(self):
        self.assertEqual(holm([0.01, None, 0.02]), [0.02, None, 0.02])
        self.assertEqual(holm([0.6, 0.7]), [1.0, 1.0])


class StudyBuildTests(unittest.TestCase):
    def setUp(self):
        self.cands = study.candidate_cases(DOC, support.DATA)

    def test_every_flagged_user_in_every_scenario_is_a_candidate(self):
        self.assertEqual(len(self.cands), 5 + 5 + 1)  # s1: a,b,d,f,h   s2: a,b,d,f,h   s3: h

    def test_selection_spreads_across_tiers_and_is_reproducible(self):
        picked = study.select_cases(self.cands, 3, seed=4)
        self.assertEqual(len({c["tier"] for c in picked}), 3)
        again = study.select_cases(study.candidate_cases(DOC, support.DATA), 3, seed=4)
        self.assertEqual([(c["scenario"], c["user"]) for c in picked], [(c["scenario"], c["user"]) for c in again])

    def test_asking_for_more_cases_than_exist_returns_what_exists(self):
        self.assertEqual(len(study.select_cases(self.cands, 99, seed=1)), len(self.cands))

    def test_latin_square_is_balanced(self):
        plan = study.assign(9, 6)
        for i in range(6):  # every case is seen in every condition by 3 of the 9 reviewers
            seen = [plan[r][i] for r in range(9)]
            self.assertEqual({c: seen.count(c) for c in study.CONDITIONS}, {"none": 3, "per_post": 3, "full": 3})
        for r in range(9):  # every reviewer sees every condition twice
            self.assertEqual({c: plan[r].count(c) for c in study.CONDITIONS}, {"none": 2, "per_post": 2, "full": 2})

    def case_with_history(self):
        return next(c for c in self.cands if c["scenario"] == "s2" and c["user"] == "u_syn_h")

    def test_the_three_explanations(self):
        case = self.case_with_history()
        none, per_post, full = (study.explanation(case, c) for c in study.CONDITIONS)
        head = f"Recommended action: {study._label(case['tier'])}"
        for text in (none, per_post, full):
            self.assertTrue(text.startswith(head))  # the decision itself never differs
        self.assertIn("No explanation", none)
        self.assertNotIn("flagged", none)
        self.assertIn("syn_post_002", per_post)  # the latest post only
        self.assertNotIn("syn_post_001", per_post)
        for leaked in ("risk", "influence", "contribution", "threshold"):
            self.assertNotIn(leaked, per_post.lower())
        self.assertIn("syn_post_001", full)
        self.assertIn("syn_post_002", full)
        self.assertIn("Contribution:", full)
        self.assertNotIn("u_syn_h", full)  # the pseudonym is hidden from reviewers

    def test_build_writes_blind_booklets_and_a_blank_response_sheet(self):
        doc_path = Path(tempfile.mkdtemp())
        out = doc_path / "study"
        res = study.build_study(DOC, support.DATA, out, reviewers=9, n_cases=6, seed=2)
        self.assertEqual((res["cases"], res["reviewers"], res["balanced"]), (6, 9, True))
        for r in range(1, 10):
            text = (out / f"R{r:02d}.txt").read_text(encoding="utf-8")
            for secret in ("per_post", "baseline", "condition", "u_syn_"):
                self.assertNotIn(secret, text)
            self.assertEqual(text.count("Your rating: ____"), 12)  # 6 cases x 2 questions
        with open(out / "responses.csv", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 54)
        self.assertTrue(all(r["clarity"] == "" and r["trust"] == "" for r in rows))
        key = json.loads((out / "assignments.json").read_text(encoding="utf-8"))
        self.assertEqual(len(key["assignments"]), 9)
        self.assertEqual(set(key["assignments"]["R01"].values()), set(study.CONDITIONS))

    def test_reviewers_see_the_cases_in_different_orders(self):
        out = Path(tempfile.mkdtemp()) / "study"
        study.build_study(DOC, support.DATA, out, reviewers=6, n_cases=6, seed=2)
        orders = {tuple(re.findall(r"case code (C\d\d)", (out / f"R{r:02d}.txt").read_text(encoding="utf-8")))
                  for r in range(1, 7)}
        self.assertGreater(len(orders), 1)


def rows_for(clarity, trust=None):
    """clarity = {condition: [rating per reviewer]}; one rating per reviewer per condition."""
    trust = trust or clarity
    out = []
    for cond, vals in clarity.items():
        for i, v in enumerate(vals):
            out.append({"reviewer": f"R{i + 1}", "case": "C1", "condition": cond, "clarity": v, "trust": trust[cond][i]})
    return out


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.res = sa.analyse(rows_for({"full": [5, 4, 5, 4], "per_post": [3, 3, 4, 3], "none": [1, 2, 1, 2]}))

    def test_descriptives(self):
        d = self.res["descriptives"]
        self.assertEqual(d["full"]["clarity"]["mean"], 4.5)
        self.assertEqual(d["full"]["clarity"]["median"], 4.5)
        self.assertEqual(d["per_post"]["clarity"]["mean"], 3.25)
        self.assertEqual(d["none"]["clarity"]["mean"], 1.5)

    def test_share_rating_clear_or_very_clear(self):
        d = self.res["descriptives"]
        self.assertEqual((d["full"]["pct_clear"], d["per_post"]["pct_clear"], d["none"]["pct_clear"]), (1.0, 0.25, 0.0))
        self.assertTrue(self.res["nfr_met"])

    def test_the_80_percent_target_can_be_missed(self):
        res = sa.analyse(rows_for({"full": [5, 3, 3, 3, 4], "per_post": [3] * 5, "none": [1] * 5}))
        self.assertAlmostEqual(res["nfr_clear_share"], 0.4)
        self.assertFalse(res["nfr_met"])

    def test_paired_test_on_reviewer_differences(self):
        t = next(t for t in self.res["tests"] if t["outcome"] == "clarity" and t["b"] == "per_post")
        self.assertEqual((t["reviewers"], t["n_nonzero"], t["median_diff"]), (4, 4, 1.0))  # diffs 2, 1, 1, 1
        self.assertAlmostEqual(t["p"], 2 / 16)
        self.assertAlmostEqual(t["min_p"], 2 / 16)
        self.assertGreaterEqual(t["p_holm"], t["p"])

    def test_four_tests_are_run_and_adjusted_together(self):
        self.assertEqual(len(self.res["tests"]), 4)
        self.assertTrue(all(t["p_holm"] is not None for t in self.res["tests"]))

    def test_each_reviewer_counts_once_not_once_per_rating(self):
        rows = [dict(reviewer="R1", case=f"C{i}", condition="full", clarity=v, trust=v) for i, v in enumerate([5, 3, 4])]
        self.assertEqual(sa.reviewer_means(rows, "clarity")["full"], {"R1": 4.0})

    def test_a_reviewer_missing_a_condition_is_left_out_of_the_pairs(self):
        rows = rows_for({"full": [5, 4, 5], "per_post": [3, 3, 4], "none": [1, 2, 1]})
        rows = [r for r in rows if not (r["reviewer"] == "R3" and r["condition"] == "none")]
        res = sa.analyse(rows)
        self.assertEqual(res["incomplete"], ["R3"])
        t = next(t for t in res["tests"] if t["outcome"] == "clarity" and t["b"] == "none")
        self.assertEqual(t["reviewers"], 2)

    def test_warnings_for_a_small_panel(self):
        w = sa.warnings_for(self.res)
        self.assertTrue(any("smallest possible p" in m for m in w))  # 4 reviewers: min p = 0.125
        self.assertTrue(any("only 4 reviewers" in m for m in w))

    def test_the_smallest_possible_p_warning_switches_on_at_six_differing_reviewers(self):
        five = sa.analyse(rows_for({"full": [5] * 5, "per_post": [3] * 5, "none": [1] * 5}))
        six = sa.analyse(rows_for({"full": [5] * 6, "per_post": [3] * 6, "none": [1] * 6}))
        self.assertTrue(any("never reach 0.05" in m for m in sa.warnings_for(five)))  # min p = 0.0625
        self.assertFalse(any("never reach 0.05" in m for m in sa.warnings_for(six)))  # min p = 0.031

    def test_reviewers_who_tie_do_not_count_as_differing(self):
        # 9 reviewers, but only 4 rate full above per_post: the test has just 4 usable pairs
        full = [4, 4, 4, 4, 3, 3, 3, 3, 3]
        res = sa.analyse(rows_for({"full": full, "per_post": [3] * 9, "none": [1] * 9}))
        t = next(t for t in res["tests"] if t["outcome"] == "clarity" and t["b"] == "per_post")
        self.assertEqual((t["reviewers"], t["n_nonzero"]), (9, 4))
        self.assertTrue(any("only 4 reviewer(s) differ" in m for m in sa.warnings_for(res)))

    def test_a_big_enough_clear_win_raises_no_size_warning(self):
        res = sa.analyse(rows_for({"full": [5, 5, 4, 5, 4, 5, 5, 4, 5, 4], "per_post": [3, 3, 3, 2, 3, 3, 4, 3, 2, 3],
                                   "none": [1, 2, 1, 1, 2, 1, 2, 1, 1, 2]}))
        self.assertEqual(sa.warnings_for(res), [])
        self.assertTrue(all(t["p_holm"] < 0.05 for t in res["tests"]))


class LoadResponsesTests(unittest.TestCase):
    KEY = {"assignments": {"R1": {"C1": "full", "C2": "none"}}}

    def load(self, lines):
        d = Path(tempfile.mkdtemp())
        p = d / "responses.csv"
        p.write_text("reviewer_id,case_id,clarity,trust\n" + "\n".join(lines) + "\n", encoding="utf-8")
        return sa.load_responses(p, self.KEY)

    def test_good_rows_get_their_condition_and_blank_rows_are_counted(self):
        rows, blank = self.load(["R1,C1,5,4", "R1,C2,,"])
        self.assertEqual(rows, [{"reviewer": "R1", "case": "C1", "condition": "full", "clarity": 5, "trust": 4}])
        self.assertEqual(blank, 1)

    def test_bad_values_are_rejected(self):
        for bad in ("R1,C1,6,4", "R1,C1,0,4", "R1,C1,five,4", "R1,C1,4,"):
            with self.subTest(bad):
                with self.assertRaises(ValueError):
                    self.load([bad])

    def test_a_row_not_in_the_assignments_is_rejected(self):
        with self.assertRaises(ValueError):
            self.load(["R9,C1,3,3"])


if __name__ == "__main__":
    unittest.main()
