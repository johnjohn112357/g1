import unittest
from datetime import datetime, timezone
from incident_intelligence import group_reports, summarize_group, similarity, parse_date

class IncidentGroupingTests(unittest.TestCase):
    def test_jaccard_similarity(self):
        self.assertGreaterEqual(similarity("Missile strike near border", "Missile strike near border reported"), .7)
        self.assertLess(similarity("Missile strike near border", "Missile strike unrelated"), .72)

    def test_grouping_requires_two_reports(self):
        rows=[{"id":1,"title":"Missile strike near border","domain":"A"},{"id":2,"title":"Missile strike near border reported","domain":"B"},{"id":3,"title":"Weather outlook for weekend","domain":"C"}]
        groups=group_reports(rows)
        self.assertEqual(len(groups),1)
        self.assertEqual(len(groups[0]["reports"]),2)

    def test_date_formats(self):
        self.assertEqual(parse_date("20261113093407"),datetime(2026,11,13,9,34,7,tzinfo=timezone.utc))
        self.assertIsNotNone(parse_date("2026-11-13T09:34:07Z"))
        self.assertIsNone(parse_date("not-a-date"))

    def test_grouping_respects_age_window(self):
        rows=[{"id":1,"title":"Missile strike near border","last_seen":"2026-11-13T09:00:00Z"},{"id":2,"title":"Missile strike near border reported","last_seen":"2026-10-01T09:00:00Z"}]
        self.assertEqual(group_reports(rows),[])

    def test_summary_has_dates_and_no_independence_claim(self):
        s=summarize_group({"representative":"Cyber incident","reports":[{"id":1,"title":"Cyber incident","domain":"A","url":"https://a","seendate":"20261113090000"},{"id":2,"title":"Cyber incident reported","domain":"B","url":"https://b","seendate":"20261113093000"}]})
        self.assertEqual(s["publisher_count"],2)
        self.assertIn("not been verified",s["evidence_note"])
        self.assertTrue(s["id"].startswith("inc-"))
        self.assertIsNotNone(s["first_reported"])
        self.assertEqual(len(s["timeline"]),2)

    def test_single_report_not_clustered(self):
        self.assertEqual(group_reports([{"id":1,"title":"A reported event"}]),[])

if __name__=="__main__":unittest.main()
