import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from api import live, service
from tools import demo_classifier as demo


def comment(cid, author, text="hello", media=(), type="comment"):
    return dict(comment_id=cid, post_id="p1", type=type, thread_root_id=None, author_id=author, reply_to_id=None,
                reply_to_ambiguous=False, mentions=[], text=text, media=list(media))


class LiveBase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        for attr, value in (("DATA_DIR", self.dir), ("STORE_PATH", self.dir / "risk_store.json")):
            p = mock.patch.object(service, attr, value)
            p.start()
            self.addCleanup(p.stop)
        self.t1, self.c1 = support.load("synthetic_thread.json"), support.load("synthetic_classifier.json")

    def risks(self):
        return {u["user"]: u["risk"] for u in service.list_users("none")}


EXPECTED = {"u_syn_a": 5.28, "u_syn_h": 2.34, "u_syn_f": 1.0, "u_syn_d": 0.85, "u_syn_b": 0.72}


class CaptureAndClassifyTests(LiveBase):
    def test_a_capture_with_no_labels_yet_is_all_unclassified(self):
        s = live.store_capture(self.t1)
        self.assertEqual((s["comments"], s["unclassified"], s["users_flagged"]), (16, 16, 0))
        self.assertEqual(self.risks(), {})

    def test_labels_arriving_after_the_capture_give_the_same_scores_as_ingest(self):
        live.store_capture(self.t1)
        r = live.add_classifications(self.c1)
        self.assertEqual(r["posts_rescored"], ["syn_post_001"])
        self.assertEqual(self.risks(), EXPECTED)

    def test_labels_arriving_before_the_capture_give_the_same_scores(self):
        live.add_classifications(self.c1)
        self.assertEqual(self.risks(), {})  # no capture yet, so nothing to score
        s = live.store_capture(self.t1)
        self.assertEqual(s["unclassified"], 1)  # comment 9000014 never got a label
        self.assertEqual(self.risks(), EXPECTED)

    def test_capturing_the_same_post_again_changes_nothing(self):
        live.store_capture(self.t1)
        live.add_classifications(self.c1)
        live.store_capture(self.t1)
        live.add_classifications(self.c1)
        self.assertEqual(self.risks(), EXPECTED)

    def test_a_growing_thread_replaces_the_earlier_capture(self):
        live.add_classifications(self.c1)
        early = dict(self.t1, comments=self.t1["comments"][:5])  # a's comment and replies to it
        live.store_capture(early)
        before = self.risks()
        self.assertNotIn("u_syn_f", before)  # f's comment was not captured yet
        live.store_capture(self.t1)
        self.assertEqual(self.risks(), EXPECTED)

    def test_a_sources_newer_label_replaces_its_older_one(self):
        live.store_capture(self.t1)
        live.add_classifications(self.c1)
        weaker = [dict(r) for r in self.c1 if r["comment_id"] == "9000001"]
        weaker[0]["confidence_score"] = 0.6
        live.add_classifications(weaker)
        self.assertEqual(self.risks()["u_syn_a"], round((0.6 + 0.88 + 0.86) * 2, 3))  # influence 1.0

    def test_two_sources_on_one_comment_keep_the_stronger_severity(self):
        live.store_capture(self.t1)
        live.add_classifications(self.c1)  # 9000010 has a text label (0.55) and a meme label (0.70)
        stored = json.loads((self.dir / live.CLASSIFIER).read_text())
        self.assertEqual({r["source_component"] for r in stored["9000010"]}, {"sinhala-english", "meme"})
        self.assertEqual(self.risks()["u_syn_h"], 2.34)  # 0.70 + 0.52 + 0.58 + 0.54, no influence

    def test_bad_records_are_rejected_and_nothing_is_stored(self):
        live.store_capture(self.t1)
        for bad in ([{"comment_id": "9000001"}], [], "nope",
                    [dict(self.c1[0]), dict(self.c1[1], predicted_category="banana")]):
            with self.subTest(str(bad)[:30]):
                with self.assertRaises(ValueError):
                    live.add_classifications(bad)
        self.assertFalse((self.dir / live.CLASSIFIER).exists())
        self.assertEqual(self.risks(), {})

    def test_extra_fields_in_a_record_are_not_kept(self):
        live.store_capture(self.t1)
        rec = dict(self.c1[0], text="something private")
        live.add_classifications([rec])
        self.assertNotIn("something private", (self.dir / live.CLASSIFIER).read_text())

    def test_malformed_captures_are_rejected(self):
        for bad in (None, {}, {"post_id": "", "comments": []}, {"post_id": "p"}, {"post_id": "p", "comments": [{"comment_id": "1"}]},
                    {"post_id": None, "comments": []}):
            with self.subTest(str(bad)[:40]):
                with self.assertRaises(ValueError):
                    live.store_capture(bad)
        self.assertFalse((self.dir / live.CAPTURES).exists())


class PendingTests(LiveBase):
    def test_pending_gives_the_comment_and_no_author(self):
        live.store_capture(self.t1)
        items = live.pending()
        self.assertEqual(len(items), 16)
        self.assertEqual(set(items[0]), {"comment_id", "post_id", "text", "media"})

    def test_labelled_comments_leave_the_list(self):
        live.store_capture(self.t1)
        live.add_classifications(self.c1)
        self.assertEqual([i["comment_id"] for i in live.pending()], ["9000014"])

    def test_a_source_still_sees_comments_only_other_sources_have_labelled(self):
        live.store_capture(self.t1)
        live.add_classifications(self.c1)
        self.assertEqual(len(live.pending(source="meme")), 15)  # only 9000010 has a meme label
        self.assertEqual([i["comment_id"] for i in live.pending(source="sinhala-english")], ["9000014"])

    def test_kind_and_limit(self):
        cap = {"post_id": "p1", "comments": [comment("1", "a", "words"), comment("2", "b", None, [{"kind": "image"}]),
                                             comment("3", "c", "more words", [{"kind": "gif"}])]}
        live.store_capture(cap)
        self.assertEqual([i["comment_id"] for i in live.pending(kind="text")], ["1", "3"])
        self.assertEqual([i["comment_id"] for i in live.pending(kind="media")], ["2", "3"])
        self.assertEqual(len(live.pending(limit=2)), 2)
        with self.assertRaises(ValueError):
            live.pending(kind="video")
        with self.assertRaises(ValueError):
            live.pending(limit=0)


class DemoClassifierTests(LiveBase):
    def test_only_marked_comments_are_labelled(self):
        self.assertIsNone(demo.classify({"comment_id": "1", "text": "a perfectly normal comment"}))
        self.assertIsNone(demo.classify({"comment_id": "1", "text": None}))
        self.assertIsNone(demo.classify({"comment_id": "1", "text": "#testhate-banana"}))

    def test_marker_parsing(self):
        r = demo.classify({"comment_id": "7", "text": "x #testhate-political y"})
        self.assertEqual(r, {"comment_id": "7", "source_component": "demo-marker",
                             "predicted_category": "political", "confidence_score": 0.85})
        self.assertEqual(demo.classify({"comment_id": "7", "text": "#TESTHATE-Religious-0.9"})["confidence_score"], 0.9)
        self.assertEqual(demo.classify({"comment_id": "7", "text": "#testhate-racial_ethnic-.7"})["confidence_score"], 0.7)
        self.assertEqual(demo.classify({"comment_id": "7", "text": "#testhate-gender_based-1.0"})["confidence_score"], 1.0)

    def test_the_whole_loop_in_process(self):
        cap = {"post_id": "p1", "comments": [
            comment("1", "a", "hello"), comment("2", "b", "bad #testhate-political-0.9"),
            comment("3", "b", "worse #TESTHATE-religious"), comment("4", "c", None, [{"kind": "image"}])]}
        live.store_capture(cap)
        get = lambda path: live.pending(kind="text", source=demo.SOURCE)  # noqa: E731
        post = lambda path, body: live.add_classifications(body)  # noqa: E731
        self.assertEqual(demo.run_once(get, post), 2)
        self.assertEqual(self.risks(), {"b": 1.75})  # 0.90 + 0.85, thread too small for influence
        self.assertEqual(service.list_users("warning")[0]["recommended_tier"], "warning")
        self.assertEqual(demo.run_once(get, post), 0)  # nothing new to label
        self.assertEqual([i["comment_id"] for i in live.pending(kind="media")], ["4"])  # the image is left for the meme component

    def test_nothing_is_posted_when_nothing_matches(self):
        sent = []
        demo.run_once(lambda p: [{"comment_id": "1", "text": "nothing here"}], lambda p, b: sent.append(b))
        self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
