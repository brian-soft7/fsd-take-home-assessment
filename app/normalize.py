import json
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

# decided with client: everything is NY time, naive times too
TZ = ZoneInfo("America/New_York")

# 2nd one is CRM-1008, bad data
FMTS = ["%Y-%m-%d", "%m-%d/%Y", "%m/%d/%Y"]


def parse_date(s):
    if not s:
        return None
    for f in FMTS:
        try:
            return datetime.strptime(s, f).date()
        except ValueError:
            pass
    return None


def parse_time(s):
    if not s:
        return None
    for f in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, f).time()
        except ValueError:
            pass
    return None


def parse_dt(s):
    if not s:
        return None
    try:
        # fromisoformat doesn't like Z
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        return d.replace(tzinfo=TZ)
    return d.astimezone(TZ)


def clean_email(a):
    if not a or not a.strip():
        return None
    # CAL-A16 has "raj.patel[at]atlasvc.com"
    a = re.sub(r"\s*[\[(]at[\])]\s*", "@", a.strip(), flags=re.I)
    if "@" in a:
        return a.lower()
    # not an email (e.g. "external-guests"), keep as is
    return a


def get_type(loc, emails):
    # calendar has no type field, so guess from location + people
    # zoom check goes first, a zoom call between staff is still virtual
    if loc and any(w in loc.lower() for w in ("zoom", "teams", "virtual")):
        return "Virtual"
    mails = [e for e in emails if "@" in e]
    if mails and all(e.endswith("@firma.com") for e in mails):
        return "Internal"
    if loc:
        return "In-Person"
    # no clue, stay unknown. better than a wrong guess
    return None


def norm_status(s):
    # Completed and confirmed mean the same, don't flag that as a conflict
    s = (s or "").strip().lower()
    if s in ("confirmed", "scheduled", "completed"):
        return "active"
    if s == "tentative":
        return "tentative"
    if s in ("cancelled", "canceled"):
        return "cancelled"
    return None


def load_crm(r):
    # no id = can't track it, load_all skips it
    if not r.get("crm_id"):
        return None
    warns = []
    d = parse_date(r.get("meeting_date"))
    t = parse_time(r.get("meeting_time"))
    if not d:
        warns.append("bad date")
    elif r["meeting_date"] != d.isoformat():
        warns.append("date fixed")
    if not t:
        warns.append("no time")
    start = None
    if d:
        # midnight is only a placeholder, has_time tells it's not real
        start = datetime.combine(d, t or time(0, 0)).replace(tzinfo=TZ)

    # "Multiple" is not a person
    name = r.get("client_name")
    if name and name.lower() in ("multiple", "tbd", "n/a"):
        warns.append("fake client name")
        name = None
    if r.get("notes") == "":
        warns.append("empty notes")

    return {
        "src": "crm",
        "id": r["crm_id"],
        "title": r.get("subject"),
        "start": start,
        "has_time": t is not None,
        "end": None,
        "client": name,
        "company": r.get("client_company"),
        "owner": r.get("relationship_owner"),
        "type": r.get("meeting_type"),
        "type_guess": False,
        "loc": r.get("location"),
        "people": [],
        "status": r.get("status"),
        "group": norm_status(r.get("status")),
        "notes": r.get("notes") or None,
        "created": parse_dt(r.get("created_at")),
        "warns": warns,
    }


def load_cal(r):
    if not r.get("event_id"):
        return None
    warns = []
    start = parse_dt(r.get("start_time"))
    end = parse_dt(r.get("end_time"))
    if not start:
        warns.append("bad start")
    if str(r.get("start_time")).endswith("Z"):
        warns.append("utc -> NY")
    # CAL-A11 end has no seconds
    if r.get("end_time") and not re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d", r["end_time"]):
        warns.append("odd end time")

    people = []
    for a in r.get("attendees") or []:
        c = clean_email(a)
        if not c:
            continue
        if c != a:
            warns.append("fixed " + a)
        if "@" not in c:
            warns.append("not an email: " + c)
        people.append(c)
    if not people:
        warns.append("no attendees")

    loc = r.get("location")
    if not loc:
        warns.append("no location")
    org = clean_email(r.get("organizer"))

    return {
        "src": "calendar",
        "id": r["event_id"],
        "title": r.get("title"),
        "start": start,
        "has_time": True,
        "end": end,
        "client": None,
        "company": None,
        "owner": org,
        # organizer alone says nothing about type (CAL-A11)
        "type": get_type(loc, people + [org or ""] if people else []),
        # so merge won't call a wrong guess a conflict
        "type_guess": True,
        "loc": loc,
        "people": people,
        "status": r.get("status"),
        "group": norm_status(r.get("status")),
        "notes": r.get("description"),
        "recurring": bool(r.get("is_recurring")),
        "created": parse_dt(r.get("created_at")),
        "warns": warns,
    }


# key, file, loader
SOURCES = [
    ("crm", "crm_events.json", load_crm),
    ("cal", "calendar_events.json", load_cal),
]


def load_all(folder):
    out = {"skipped": []}
    for key, name, fn in SOURCES:
        rows = json.loads((Path(folder) / name).read_text(encoding="utf-8"))
        out[key] = []
        for r in rows:
            rec = fn(r)
            if rec:
                out[key].append(rec)
            else:
                out["skipped"].append({"src": key, "msg": "no id", "row": r})
    return out


def warn_list(recs):
    # flat list for the report, each warning keeps its record id
    return [{"src": r["src"], "id": r["id"], "msg": w} for r in recs for w in r["warns"]]
