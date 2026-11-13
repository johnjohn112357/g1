import unittest
from intelligence import classify, theme, cluster_events, build_brief

class IntelligenceTests(unittest.TestCase):
    def test_keyword_triage_is_transparent(self):
        r=classify("Officials report a missile strike near the border")
        self.assertEqual(r["heuristic_level"],"high")
        self.assertIn("missile",r["matched_terms"])
        self.assertEqual(r["method"],"keyword screen")
    def test_theme_detection(self):
        self.assertIn("Cyber & technology",theme("Ransomware attack disrupts internet services"))
    def test_title_clusters_require_multiple_reports(self):
        rows=[{"title":"Missile strike near border","source":"A"},{"title":"Missile strike near border reported","source":"B"},{"title":"Weather forecast","source":"C"}]
        clusters=cluster_events(rows)
        self.assertTrue(clusters)
        self.assertGreaterEqual(clusters[0]["reports"],2)
        self.assertIn("not confirmed",clusters[0]["note"])
    def test_brief_discloses_method_and_caveat(self):
        b=build_brief([{"title":"Nuclear plant security alert","source":"X"}])
        self.assertIn("keyword",b["method"].lower())
        self.assertIn("false claims",b["caveat"].lower())

if __name__=="__main__":unittest.main()
