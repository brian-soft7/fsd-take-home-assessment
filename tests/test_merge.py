import unittest
from pathlib import Path

from app.dedupe import dedupe
from app.match import match
from app.merge import FIELDS, merge_all
from app.normalize import load_all

DATA = Path(__file__).resolve().parent.parent / "data"


class TestMerge(unittest.TestCase):
    def setUp(self):
        d = load_all(DATA)
        crm, _ = dedupe(d["crm"])
        cal, _ = dedupe(d["cal"])
        self.all = merge_all(*match(crm, cal))
        self.m = {x["id"]: x for x in self.all}

    def kind(self, mid, field):
        return self.m[mid]["fields"][field]["kind"]

    def test_counts(self):
        w = [x["where"] for x in self.all]
        self.assertEqual(len(self.all), 24)
        self.assertEqual((w.count("both"), w.count("crm"), w.count("cal")), (17, 3, 4))

    def test_every_field_present(self):
        for x in self.all:
            self.assertEqual(set(x["fields"]), set(FIELDS))
            for f in x["fields"].values():
                self.assertEqual(set(f), {"crm", "cal", "show", "src", "kind", "rule", "note"})

    def test_sorted_by_time(self):
        starts = [x["start"] for x in self.all]
        self.assertEqual(starts, sorted(starts))

    def test_exact_conflicts(self):
        got = {i: x["conflicts"] for i, x in self.m.items() if x["conflicts"]}
        self.assertEqual(got, {
            "crm-1002": ["type", "loc"],  # in person vs zoom
            "crm-1004": ["start"],        # 19:00Z is 15:00 NY, crm says 14:00
            "crm-1009": ["status"],       # cancelled vs confirmed
            "crm-1016": ["start"],        # 13:00 vs 15:00
        })

    def test_cancel_wins(self):
        s = self.m["crm-1009"]["fields"]["status"]
        self.assertEqual((s["show"], s["src"]), ("Cancelled", "crm"))

    def test_start_conflict_shows_calendar(self):
        s = self.m["crm-1016"]["fields"]["start"]
        self.assertEqual(s["src"], "cal")
        self.assertIn("120 min", s["note"])
        self.assertTrue(s["show"].startswith("2025-03-27T15:00"))

    def test_missing_time_filled(self):
        self.assertEqual(self.kind("crm-1007", "start"), "filled")
        self.assertTrue(self.m["crm-1007"]["has_time"])

    def test_wording_is_not_conflict(self):
        for i in ("crm-1001", "crm-1005", "crm-1011", "crm-1015", "crm-1017"):
            self.assertEqual(self.kind(i, "loc"), "diff", i)
        self.assertEqual(self.kind("crm-1001", "status"), "diff")  # Completed vs confirmed
        self.assertEqual(self.kind("crm-1013", "owner"), "diff")   # Sarah vs Priya

    def test_more_detail_wins(self):
        self.assertEqual(self.m["crm-1005"]["fields"]["loc"]["show"], "Boston Office - Room 301")
        self.assertEqual(self.m["crm-1001"]["fields"]["loc"]["show"], "HQ - Conference Room B")

    def test_merged_duplicate(self):
        x = self.m["crm-1005"]
        self.assertEqual(x["ids"]["cal"], ["CAL-A5", "CAL-A6"])
        self.assertIn("sandra.mills@pinnaclegp.com", x["fields"]["people"]["show"])

    def test_unknown_type_is_not_conflict(self):
        # CRM-1014: calendar has no location, so no type
        f = self.m["crm-1014"]["fields"]["type"]
        self.assertEqual((f["kind"], f["show"]), ("only", "Virtual"))

    def test_single_source(self):
        x = self.m["crm-1003"]
        self.assertEqual(x["where"], "crm")
        self.assertEqual(x["fields"]["type"]["src"], "crm")
        self.assertIsNone(x["match"])
        self.assertEqual(self.m["cal-a3"]["fields"]["client"]["kind"], "empty")
        self.assertTrue(self.m["cal-a3"]["recurring"])

    def test_match_kept(self):
        self.assertGreaterEqual(self.m["crm-1001"]["match"]["score"], 0.55)
        self.assertEqual(self.m["crm-1001"]["ids"], {"crm": "CRM-1001", "cal": ["CAL-A1"]})

    def test_warns_follow_meeting(self):
        self.assertIn("date fixed", self.m["crm-1008"]["warns"])
        self.assertIn("utc -> NY", self.m["crm-1004"]["warns"])


if __name__ == "__main__":
    unittest.main()
