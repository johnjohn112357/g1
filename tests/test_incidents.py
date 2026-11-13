import unittest
from incident_intelligence import group_reports, summarize_group, similarity

class IncidentGroupingTests(unittest.TestCase):
    def test_similarity(self):
        self.assertGreaterEqual(similarity("Missile strike near border", "Missile strike near border reported"), .7)
    def test_grouping_requires_two_reports(self):
        rows=[{"id":1,"title":"Missile strike near border","domain":"A"},{"id":2,"title":"Missile strike near border reported","domain":"B"},{"id":3,"title":"Weather outlook for weekend","domain":"C"}]
        groups=group_reports(rows)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]["reports"]),2)
    def test_summary_does_not_claim_independence(self):
        s=summarize_group({"representative":"Cyber incident","reports":[{"id":1,"title":"Cyber incident","domain":"A","url":"https://a"},{"id":2,"title":"Cyber incident reported","domain":"B","url":"https://b"}]})
        self.assertEqual(s["publisher_count"],2)
        self.assertIn("not been verified",s["evidence_note"])
        self.assertTrue(s["id"].startswith("inc-"))
    def test_single_report_not_clustered(self):
        self.assertEqual(group_reports([{"id":1,"title":"A reported event"}]),[])

if __name__=="__main__":unittest.main()
