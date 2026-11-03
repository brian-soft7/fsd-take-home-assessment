import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.build import build
from app.main import app

DATA = Path(__file__).resolve().parent.parent / "data"


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # "with" runs startup, so the data is loaded
        cls.cm = TestClient(app)
        cls.c = cls.cm.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)

    def ids(self, url):
        return sorted(m["id"] for m in self.c.get(url).json()["meetings"])

    def test_list(self):
        r = self.c.get("/api/meetings").json()
        self.assertEqual((r["count"], len(r["meetings"])), (24, 24))

    def test_filter_where(self):
        self.assertEqual(len(self.ids("/api/meetings?where=both")), 17)
        self.assertEqual(len(self.ids("/api/meetings?where=crm")), 3)
        self.assertEqual(len(self.ids("/api/meetings?where=cal")), 4)

    def test_filter_conflict(self):
        self.assertEqual(self.ids("/api/meetings?conflict=true"), ["crm-1002", "crm-1004", "crm-1009", "crm-1016"])
        self.assertEqual(len(self.ids("/api/meetings?conflict=false")), 20)

    def test_filters_combine(self):
        self.assertEqual(self.ids("/api/meetings?where=crm&conflict=true"), [])

    def test_search(self):
        # client Meridian Capital has two meetings
        self.assertEqual(self.ids("/api/meetings?q=meridian"), ["crm-1001", "crm-1007"])
        self.assertEqual(self.ids("/api/meetings?q=MERIDIAN"), ["crm-1001", "crm-1007"])  # any case
        self.assertEqual(self.ids("/api/meetings?q=weekly"), ["cal-a18", "cal-a3"])  # title

    def test_bad_filter(self):
        self.assertEqual(self.c.get("/api/meetings?where=nope").status_code, 422)

    def test_one(self):
        r = self.c.get("/api/meetings/crm-1002").json()
        self.assertEqual(r["conflicts"], ["type", "loc"])
        self.assertEqual(r["fields"]["type"]["crm"], "In-Person")
        self.assertEqual(r["fields"]["type"]["cal"], "Virtual")

    def test_one_any_case(self):
        self.assertEqual(self.c.get("/api/meetings/CRM-1002").status_code, 200)

    def test_one_missing(self):
        self.assertEqual(self.c.get("/api/meetings/nope").status_code, 404)

    def test_report(self):
        r = self.c.get("/api/report").json()
        k = r["counts"]
        self.assertEqual((k["crm_rows"], k["cal_rows"], k["cal_after_dedupe"]), (20, 22, 21))
        self.assertEqual((k["meetings"], k["both"], k["crm_only"], k["cal_only"], k["conflicts"]), (24, 17, 3, 4, 4))
        self.assertEqual(r["dups"], [{"src": "calendar", "kept": "CAL-A5", "dropped": ["CAL-A6"]}])
        self.assertEqual(r["timezone"], "America/New_York")
        self.assertEqual(k["warns"], len(r["warns"]))

    def test_report_warns_have_ids(self):
        w = self.c.get("/api/report").json()["warns"]
        self.assertIn({"src": "crm", "id": "CRM-1008", "msg": "date fixed"}, w)
        self.assertIn({"src": "calendar", "id": "CAL-A20", "msg": "not an email: external-guests"}, w)
        self.assertIn({"src": "calendar", "id": "CAL-A16", "msg": "fixed raj.patel[at]atlasvc.com"}, w)

    def test_page(self):
        r = self.c.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/html", r.headers["content-type"])
        self.assertIn("/static/app.js", r.text)

    def test_script(self):
        r = self.c.get("/static/app.js")
        self.assertEqual(r.status_code, 200)
        self.assertIn("/api/meetings", r.text)

    def test_sync(self):
        r = self.c.post("/api/sync").json()
        self.assertEqual(r["counts"]["meetings"], 24)
        self.assertEqual(self.c.get("/api/meetings").json()["count"], 24)


class TestBuild(unittest.TestCase):
    def test_other_folder(self):
        # one crm row only, no calendar
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "crm_events.json").write_text(json.dumps([
                {"crm_id": "X1", "subject": "Hi", "meeting_date": "2025-01-02", "meeting_time": "09:00"},
                {"subject": "no id"},
            ]))
            Path(tmp, "calendar_events.json").write_text("[]")
            r = build(tmp)
        self.assertEqual([m["id"] for m in r["meetings"]], ["x1"])
        self.assertEqual(len(r["report"]["skipped"]), 1)


if __name__ == "__main__":
    unittest.main()
