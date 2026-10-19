import unittest

import support  # noqa: F401  (sets up the import path)
from graph.build_graph import POST, build_graph


def c(cid, author, type="comment", root=None, reply_to=None, mentions=()):
    return dict(comment_id=cid, author_id=author, type=type, thread_root_id=root,
                reply_to_id=reply_to, mentions=list(mentions))


def cap(*comments):
    return {"post_id": "p1", "comments": list(comments)}


class BuildGraphTests(unittest.TestCase):
    def test_top_level_comment_points_at_the_post(self):
        g = build_graph(cap(c("1", "a")))
        self.assertTrue(g.has_edge("a", POST))

    def test_reply_points_at_its_target(self):
        g = build_graph(cap(c("1", "a"), c("2", "b", "reply", "1", "a")))
        self.assertTrue(g.has_edge("b", "a"))
        self.assertFalse(g.has_edge("b", POST))

    def test_mention_of_the_reply_target_is_not_counted_twice(self):
        g = build_graph(cap(c("1", "a"), c("2", "b", "reply", "1", "a", mentions=["a"])))
        self.assertEqual(g["b"]["a"]["weight"], 1)

    def test_mention_of_a_third_user_adds_an_edge(self):
        g = build_graph(cap(c("1", "a"), c("2", "b", "reply", "1", "a", mentions=["d"])))
        self.assertTrue(g.has_edge("b", "a"))
        self.assertTrue(g.has_edge("b", "d"))

    def test_repeated_interactions_add_weight(self):
        g = build_graph(cap(c("1", "a"), c("2", "b", "reply", "1", "a"), c("3", "b", "reply", "1", "a")))
        self.assertEqual(g["b"]["a"]["weight"], 2)

    def test_self_reply_makes_no_edge(self):
        g = build_graph(cap(c("1", "a"), c("2", "a", "reply", "1", "a")))
        self.assertFalse(g.has_edge("a", "a"))
        self.assertIn("a", g.nodes)

    def test_unresolved_target_falls_back_to_the_root_author(self):
        g = build_graph(cap(c("1", "a"), c("2", "b", "reply", "1", None)))
        self.assertTrue(g.has_edge("b", "a"))

    def test_unresolved_target_with_missing_root_falls_back_to_the_post(self):
        g = build_graph(cap(c("2", "b", "reply", "999", None)))
        self.assertTrue(g.has_edge("b", POST))

    def test_real_sample_thread(self):
        g = build_graph(support.load("sample_thread.json"))
        self.assertEqual(g.number_of_nodes(), 10)  # 9 users + the post
        self.assertEqual(g.number_of_edges(), 11)


if __name__ == "__main__":
    unittest.main()
