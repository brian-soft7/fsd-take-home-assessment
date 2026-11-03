import json
import tempfile
import unittest
from datetime import date, time
from pathlib import Path

from app.normalize import (
    clean_email, get_type, load_all, load_cal, load_crm,
    norm_status, parse_date, parse_dt, parse_time, warn_list,
)

DATA = Path(__file__).resolve().parent.parent / "data"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


class TestParsers(unittest.TestCase):
    def test_date(self):
        self.assertEqual(parse_date("2025-03-10"), date(2025, 3, 10))
        self.assertEqual(parse_date("03-15/2025"), date(2025, 3, 15))  # CRM-1008
        self.assertIsNone(parse_date("nope"))
        self.assertIsNone(parse_date(None))

    def test_time(self):
        self.assertEqual(parse_time("14:00"), time(14, 0))
        self.assertIsNone(parse_time(None))  # CRM-1007
        self.assertIsNone(parse_time("noon"))

    def test_dt(self):
        d = parse_dt("2025-03-13T19:00:00Z")  # CAL-A4, EDT so 15:00
        self.assertEqual((d.hour, d.day), (15, 13))
        self.assertEqual(parse_dt("2025-03-14T20:00").hour, 20)  # CAL-A11 end
        self.assertIsNone(parse_dt("nope"))
        self.assertIsNone(parse_dt(None))


class TestHelpers(unittest.TestCase):
    def test_email(self):
        self.assertEqual(clean_email("raj.patel[at]atlasvc.com"), "raj.patel@atlasvc.com")
        self.assertEqual(clean_email(" Sarah.Chen@Firma.com "), "sarah.chen@firma.com")
        self.assertEqual(clean_email("external-guests"), "external-guests")
        self.assertIsNone(clean_email("  "))
        self.assertIsNone(clean_email(None))

    def test_type(self):
        self.assertEqual(get_type("Zoom - https://zoom.us/j/1", ["a@firma.com", "b@x.com"]), "Virtual")
        self.assertEqual(get_type("Virtual - Microsoft Teams", ["a@firma.com"]), "Virtual")
        self.assertEqual(get_type("HQ - Room 4A", ["a@firma.com"]), "Internal")
        self.assertEqual(get_type("NYC Office", ["a@firma.com", "e@horizonwp.com"]), "In-Person")
        self.assertIsNone(get_type(None, ["a@firma.com", "m@evergreencap.com"]))  # CAL-A15
        self.assertIsNone(get_type(None, []))  # CAL-A11

    def test_status(self):
        self.assertEqual(norm_status("Completed"), "active")
        self.assertEqual(norm_status("confirmed"), "active")
        self.assertEqual(norm_status("Tentative"), "tentative")
        self.assertEqual(norm_status("Cancelled"), "cancelled")
        self.assertIsNone(norm_status(None))


class TestLoadCrm(unittest.TestCase):
    def setUp(self):
        self.rows = {r["crm_id"]: load_crm(r) for r in load("crm_events.json")}

    def test_all_loaded(self):
        self.assertEqual(len(self.rows), 20)

    def test_bad_date(self):
        r = self.rows["CRM-1008"]
        self.assertEqual(r["start"].date(), date(2025, 3, 15))
        self.assertIn("date fixed", r["warns"])

    def test_no_time(self):
        r = self.rows["CRM-1007"]
        self.assertFalse(r["has_time"])
        self.assertIn("no time", r["warns"])

    def test_fake_client(self):
        r = self.rows["CRM-1017"]
        self.assertIsNone(r["client"])
        self.assertIn("fake client name", r["warns"])

    def test_empty_notes(self):
        r = self.rows["CRM-1010"]
        self.assertIsNone(r["notes"])
        self.assertIn("empty notes", r["warns"])

    def test_normal_row(self):
        r = self.rows["CRM-1001"]
        self.assertEqual((r["start"].hour, r["group"], r["warns"]), (14, "active", []))


class TestLoadCal(unittest.TestCase):
    def setUp(self):
        self.rows = {r["event_id"]: load_cal(r) for r in load("calendar_events.json")}

    def test_all_loaded(self):
        self.assertEqual(len(self.rows), 22)

    def test_utc(self):
        r = self.rows["CAL-A4"]
        self.assertEqual(r["start"].hour, 15)
        self.assertIn("utc -> NY", r["warns"])

    def test_bad_email(self):
        r = self.rows["CAL-A16"]
        self.assertIn("raj.patel@atlasvc.com", r["people"])
        self.assertIn("fixed raj.patel[at]atlasvc.com", r["warns"])

    def test_label_attendee(self):
        r = self.rows["CAL-A20"]
        self.assertIn("external-guests", r["people"])
        self.assertIn("not an email: external-guests", r["warns"])

    def test_sparse_row(self):
        r = self.rows["CAL-A11"]
        self.assertIn("odd end time", r["warns"])
        self.assertIn("no location", r["warns"])
        self.assertIn("no attendees", r["warns"])
        self.assertIsNone(r["type"])

    def test_types(self):
        self.assertEqual(self.rows["CAL-A2"]["type"], "Virtual")  # zoom link
        self.assertEqual(self.rows["CAL-A7"]["type"], "Internal")
        self.assertEqual(self.rows["CAL-A12"]["type"], "In-Person")

    def test_type_is_guess(self):
        self.assertTrue(self.rows["CAL-A2"]["type_guess"])
        crm = load_crm(load("crm_events.json")[0])
        self.assertFalse(crm["type_guess"])


class TestLoadAll(unittest.TestCase):
    def test_real_data(self):
        d = load_all(DATA)
        self.assertEqual((len(d["crm"]), len(d["cal"]), len(d["skipped"])), (20, 22, 0))

    def test_no_id_skipped(self):
        # row without id must not crash, goes to skipped
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "crm_events.json").write_text(json.dumps([{"subject": "x"}]))
            Path(tmp, "calendar_events.json").write_text(json.dumps([{"title": "y"}]))
            d = load_all(tmp)
        self.assertEqual((len(d["crm"]), len(d["cal"])), (0, 0))
        self.assertEqual([s["src"] for s in d["skipped"]], ["crm", "cal"])

    def test_warn_list(self):
        d = load_all(DATA)
        w = warn_list(d["crm"] + d["cal"])
        self.assertIn({"src": "crm", "id": "CRM-1008", "msg": "date fixed"}, w)
        self.assertIn({"src": "calendar", "id": "CAL-A4", "msg": "utc -> NY"}, w)


if __name__ == "__main__":
    unittest.main()
