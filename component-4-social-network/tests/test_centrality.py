import unittest

import support
from centrality.centrality import (centrality_table, influence_scores, thread_big_enough,
                                   thread_checks)
from graph.build_graph import POST, build_graph

LINDA = "u_71364afa66dc0a64"


class CentralityTests(unittest.TestCase):
    def setUp(self):
        self.sample = support.load("sample_thread.json")
        self.rows = centrality_table(build_graph(self.sample))

    def test_post_node_is_not_ranked(self):
        self.assertNotIn(POST, [r["user"] for r in self.rows])

    def test_most_replied_to_user_ranks_first(self):
        top = self.rows[0]
        self.assertEqual(top["user"], LINDA)
        self.assertEqual(top["in_degree"], 3)

    def test_betweenness_matches_the_hand_calculation(self):
        # Linda lies on 5 shortest paths; normalised by (10-1)(10-2) = 72
        self.assertAlmostEqual(self.rows[0]["betweenness"], 5 / 72, places=3)

    def test_users_nobody_replied_to_have_zero_betweenness(self):
        others = [r for r in self.rows if r["user"] != LINDA and r["in_degree"] == 0]
        self.assertTrue(others)
        self.assertTrue(all(r["betweenness"] == 0 for r in others))

    def test_size_rule(self):
        self.assertFalse(thread_big_enough(self.sample))  # 12 comments
        self.assertTrue(thread_big_enough(support.load("synthetic_thread.json")))  # 16 comments, 8 users
        self.assertFalse(thread_big_enough(support.load("synthetic_thread_2.json")))  # 5 comments
        self.assertTrue(any("12 comments" in m for m in thread_checks(self.sample)))

    def test_influence_is_relative_to_the_thread_maximum(self):
        rows = [{"user": "a", "in_degree_c": 0.5, "betweenness": 0.2},
                {"user": "b", "in_degree_c": 0.25, "betweenness": 0.0}]
        infl = influence_scores(rows)
        self.assertEqual(infl["a"], (1.0, 1.0, 1.0))
        self.assertEqual(infl["b"], (0.5, 0.0, 0.25))

    def test_influence_is_zero_when_nobody_has_any(self):
        rows = [{"user": "a", "in_degree_c": 0.0, "betweenness": 0.0}]
        self.assertEqual(influence_scores(rows)["a"], (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
