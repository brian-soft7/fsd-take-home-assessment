import unittest
from pathlib import Path

from app.dedupe import dedupe
from app.match import THRESH, loc_rel, match, score
from app.normalize import load_all

DATA = Path(__file__).resolve().parent.parent / "data"


class TestLocRel(unittest.TestCase):
    def test_rel(self):
        self.assertEqual(loc_rel("Microsoft Teams", "Microsoft Teams"), "same")
        self.assertEqual(loc_rel("HQ - Conference Room B", "Conference Room B"), "more detail")
        self.assertEqual(loc_rel("Zoom", "Zoom - https://zoom.us/j/11223344"), "same")  # link ignored
        self.assertEqual(loc_rel("The Palm - DC", "The Palm Restaurant"), "similar")
        self.assertEqual(loc_rel("NYC Office - 30th Floor", "Zoom - https://zoom.us/j/1"), "different")
        self.assertEqual(loc_rel(None, "Zoom"), "missing")


class TestMatch(unittest.TestCase):
    def setUp(self):
        d = load_all(DATA)
        self.crm, _ = dedupe(d["crm"])
        self.cal, _ = dedupe(d["cal"])
        self.c = {r["id"]: r for r in self.crm}
        self.k = {r["id"]: r for r in self.cal}
        self.pairs, self.crm_left, self.cal_left = match(self.crm, self.cal)
        self.by_crm = {p["crm"]["id"]: p for p in self.pairs}

    def test_counts(self):
        self.assertEqual(len(self.pairs), 17)
        self.assertEqual(len(self.crm_left), 3)
        self.assertEqual(len(self.cal_left), 4)

    def test_left_over(self):
        self.assertEqual(sorted(r["id"] for r in self.crm_left), ["CRM-1003", "CRM-1010", "CRM-1020"])
        # two weekly syncs, the reception, roadshow prep
        self.assertEqual(sorted(r["id"] for r in self.cal_left), ["CAL-A11", "CAL-A18", "CAL-A19", "CAL-A3"])

    def test_one_to_one(self):
        self.assertEqual(len({p["crm"]["id"] for p in self.pairs}), 17)
        self.assertEqual(len({p["cal"]["id"] for p in self.pairs}), 17)

    def test_known_pairs(self):
        want = {
            "CRM-1001": "CAL-A1", "CRM-1002": "CAL-A2", "CRM-1004": "CAL-A4",
            "CRM-1005": "CAL-A5",  # A5 holds the merged A6
            "CRM-1006": "CAL-A7", "CRM-1007": "CAL-A8", "CRM-1008": "CAL-A9",
            "CRM-1009": "CAL-A10", "CRM-1011": "CAL-A12", "CRM-1012": "CAL-A13",
            "CRM-1013": "CAL-A14", "CRM-1014": "CAL-A15", "CRM-1015": "CAL-A16",
            "CRM-1016": "CAL-A17", "CRM-1017": "CAL-A20", "CRM-1018": "CAL-A21",
            "CRM-1019": "CAL-A22",
        }
        got = {i: p["cal"]["id"] for i, p in self.by_crm.items()}
        self.assertEqual(got, want)

    def test_same_client_other_day_scores_zero(self):
        self.assertEqual(score(self.c["CRM-1001"], self.k["CAL-A8"])[0], 0)  # David Park 3/10 vs 3/18
        self.assertEqual(score(self.c["CRM-1008"], self.k["CAL-A16"])[0], 0)  # Lisa Tran 3/15 vs 3/26

    def test_time_is_a_hint_only(self):
        # CRM-1016 says 13:00, calendar says 15:00
        p = self.by_crm["CRM-1016"]
        self.assertGreaterEqual(p["score"], THRESH)

    def test_no_title_overlap_still_matches(self):
        # "Quarterly Business Review" vs "QBR - Q1 Wrap", alias + time + room + owner
        self.assertIn("CRM-1019", self.by_crm)

    def test_missing_time_matches_on_date_and_people(self):
        p = self.by_crm["CRM-1007"]
        self.assertIn("crm has no time", p["why"])

    def test_cancelled_still_pairs(self):
        # status is for the merge step, not for matching
        self.assertIn("CRM-1009", self.by_crm)

    def test_weak_candidate_stays_below(self):
        # Rachel Torres intro call at 15:00 vs internal pipeline review at 16:00
        s, _ = score(self.c["CRM-1003"], self.k["CAL-A7"])
        self.assertLess(s, THRESH)

    def test_all_matches_are_clear(self):
        # lowest match should be well over the bar
        self.assertGreaterEqual(min(p["score"] for p in self.pairs), 0.8)

    def test_reasons_kept(self):
        self.assertIn("same day", self.by_crm["CRM-1001"]["why"])


if __name__ == "__main__":
    unittest.main()
