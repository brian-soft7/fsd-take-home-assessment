import unittest
from pathlib import Path

from app.dedupe import dedupe, is_dup
from app.normalize import load_all

DATA = Path(__file__).resolve().parent.parent / "data"


class TestDedupe(unittest.TestCase):
    def setUp(self):
        d = load_all(DATA)
        self.crm = d["crm"]
        self.cal = d["cal"]
        self.c = {r["id"]: r for r in self.crm + self.cal}

    def test_pinnacle_is_dup(self):
        self.assertTrue(is_dup(self.c["CAL-A5"], self.c["CAL-A6"]))

    def test_recurring_not_dup(self):
        # same title and people, different weeks
        self.assertFalse(is_dup(self.c["CAL-A3"], self.c["CAL-A18"]))

    def test_same_client_other_day_not_dup(self):
        self.assertFalse(is_dup(self.c["CRM-1001"], self.c["CRM-1007"]))  # David Park
        self.assertFalse(is_dup(self.c["CRM-1004"], self.c["CRM-1018"]))  # Patricia Langley

    def test_same_day_other_time_not_dup(self):
        self.assertFalse(is_dup(self.c["CAL-A19"], self.c["CAL-A20"]))  # 3/28 14:00 vs 19:00

    def test_missing_date_not_dup(self):
        bad = dict(self.c["CRM-1001"], start=None)
        self.assertFalse(is_dup(bad, self.c["CRM-1001"]))

    def test_crm_has_no_dups(self):
        out, dups = dedupe(self.crm)
        self.assertEqual(len(out), 20)
        self.assertEqual(dups, [])

    def test_calendar_merges_one_pair(self):
        out, dups = dedupe(self.cal)
        self.assertEqual(len(out), 21)
        self.assertEqual(dups, [{"src": "calendar", "kept": "CAL-A5", "dropped": ["CAL-A6"]}])

    def test_merged_record(self):
        out, _ = dedupe(self.cal)
        m = [r for r in out if r["id"] == "CAL-A5"][0]
        self.assertEqual(m["ids"], ["CAL-A5", "CAL-A6"])
        self.assertIn("sandra.mills@pinnaclegp.com", m["people"])  # from A6
        self.assertEqual(m["loc"], "Boston Office - Room 301")  # more detail than A6
        self.assertIn("merged CAL-A6", m["warns"])
        self.assertEqual(m["start"].hour, 11)
        self.assertEqual(m["start"].minute, 0)  # original, not A6's 11:30

    def test_input_not_changed(self):
        before = [dict(r) for r in self.cal]
        dedupe(self.cal)
        self.assertEqual(self.cal, before)

    def test_single_record_gets_ids(self):
        out, _ = dedupe(self.cal)
        m = [r for r in out if r["id"] == "CAL-A1"][0]
        self.assertEqual(m["ids"], ["CAL-A1"])


if __name__ == "__main__":
    unittest.main()
