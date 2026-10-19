import tempfile
import unittest
from pathlib import Path
from unittest import mock

import support
from api import service
from escalation import review


class ServiceTests(unittest.TestCase):
    """Runs the service against a throwaway folder, never the real data/captures."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        d = Path(tmp.name)
        for target, attr, value in [
            (service, "DATA_DIR", d),
            (service, "STORE_PATH", d / "risk_store.json"),
            (review, "LOG_PATH", d / "review_log.jsonl"),
        ]:
            p = mock.patch.object(target, attr, value)
            p.start()
            self.addCleanup(p.stop)
        self.t1, self.c1 = support.load("synthetic_thread.json"), support.load("synthetic_classifier.json")
        self.t2, self.c2 = support.load("synthetic_thread_2.json"), support.load("synthetic_classifier_2.json")

    def risks(self, min_tier="none"):
        return {u["user"]: u["risk"] for u in service.list_users(min_tier)}

    def test_ingest_reports_what_it_did(self):
        r = service.ingest(self.t1, self.c1)
        self.assertEqual((r["post_id"], r["comments"], r["unclassified"], r["users_flagged"]),
                         ("syn_post_001", 16, 1, 5))
        self.assertTrue(r["centrality_applied"])

    def test_ingest_twice_gives_the_same_result(self):
        service.ingest(self.t1, self.c1)
        first = self.risks()
        service.ingest(self.t1, self.c1)
        self.assertEqual(self.risks(), first)

    def test_malformed_input_is_a_value_error(self):
        with self.assertRaises(ValueError):
            service.ingest({"comments": []}, [])  # no post_id
        with self.assertRaises(ValueError):
            service.ingest(self.t1, [{"comment_id": "1"}])  # incomplete classifier record

    def test_users_are_ranked_and_filterable(self):
        service.ingest(self.t1, self.c1)
        users = service.list_users("warning")
        self.assertEqual([u["user"] for u in users], ["u_syn_a", "u_syn_h", "u_syn_f"])
        self.assertEqual([u["recommended_tier"] for u in users], ["flag", "warning", "warning"])
        self.assertEqual([u["user"] for u in service.list_users("flag")], ["u_syn_a"])
        with self.assertRaises(ValueError):
            service.list_users("ban")

    def test_justification_is_returned_with_its_text_and_status(self):
        service.ingest(self.t1, self.c1)
        j = service.get_justification("u_syn_a")
        self.assertEqual((j["tier"], j["risk"], j["review_status"]), ("flag", 5.28, "pending"))
        self.assertIn("recommendation only", j["text"])
        with self.assertRaises(service.NotFound):
            service.get_justification("u_nobody")

    def test_accepting_marks_the_user_reviewed(self):
        service.ingest(self.t1, self.c1)
        entry = service.record_decision("u_syn_a", "accept", "m1")
        self.assertEqual(entry["final_tier"], "flag")
        self.assertEqual(service.get_justification("u_syn_a")["review_status"], "reviewed")
        self.assertEqual(len(service.decisions_for("u_syn_a")), 1)

    def test_override_rules_are_enforced_through_the_service(self):
        service.ingest(self.t1, self.c1)
        with self.assertRaises(ValueError):
            service.record_decision("u_syn_h", "override", "m1", "", "none")
        with self.assertRaises(service.NotFound):
            service.record_decision("u_nobody", "accept", "m1")
        self.assertEqual(service.decisions_for("u_syn_h"), [])  # nothing was logged
        e = service.record_decision("u_syn_h", "override", "m1", "context was banter", "none")
        self.assertEqual((e["recommended_tier"], e["final_tier"]), ("warning", "none"))

    def test_a_review_goes_stale_when_risk_rises(self):
        service.ingest(self.t2, self.c2)
        service.record_decision("u_syn_h", "accept", "m1")
        self.assertEqual(service.get_justification("u_syn_h")["review_status"], "reviewed")
        stronger = [dict(r) for r in self.c2]
        for r in stronger[:3]:
            r["confidence_score"] = 0.9
        service.ingest(self.t2, stronger)
        self.assertEqual(service.get_justification("u_syn_h")["review_status"], "changed_since_review")

    def test_real_data_folder_is_untouched(self):
        service.ingest(self.t1, self.c1)
        service.record_decision("u_syn_a", "accept", "m1")
        self.assertFalse((support.DATA / "captures").exists())


if __name__ == "__main__":
    unittest.main()
