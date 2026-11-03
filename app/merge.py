from .match import loc_rel, squash, words

# kind of each field:
#   same     both agree
#   only     only one source has it
#   filled   one source was missing it, the other filled it in
#   info     both have text, both are shown
#   diff     same fact, worded differently (not a real problem)
#   conflict real disagreement, flagged


def fld(c_val, k_val, show, src, kind, rule="", note=""):
    return {"crm": c_val, "cal": k_val, "show": show, "src": src,
            "kind": kind, "rule": rule, "note": note}


def only(c, k, c_val, k_val):
    # record exists in one source only
    r = c or k
    show = c_val if c else k_val
    if show in (None, "", []):
        return fld(c_val, k_val, None, None, "empty", "no value")
    return fld(c_val, k_val, show, r["src"], "only", "only source")


def iso(r):
    if not r["start"]:
        return None
    return r["start"].isoformat() if r["has_time"] else r["start"].date().isoformat()


def f_title(c, k):
    if not (c and k):
        return only(c, k, c and c["title"], k and k["title"])
    if (c["title"] or "").lower() == (k["title"] or "").lower():
        return fld(c["title"], k["title"], c["title"], "both", "same")
    return fld(c["title"], k["title"], c["title"], "crm", "diff",
               "crm title is shown", "each system words the title its own way")


def f_start(c, k):
    if not (c and k):
        return only(c, k, c and iso(c), k and iso(k))
    if not c["has_time"]:
        return fld(iso(c), iso(k), iso(k), "cal", "filled", "calendar fills the time", "crm has a date but no time")
    gap = abs((c["start"] - k["start"]).total_seconds()) / 60
    if gap == 0:
        return fld(iso(c), iso(k), iso(k), "both", "same")
    # calendar is the invite people really get
    return fld(iso(c), iso(k), iso(k), "cal", "conflict", "calendar wins for time",
               "start times are %d min apart" % gap)


def f_end(c, k):
    return only(None, k, None, k and k["end"] and k["end"].isoformat())


def f_type(c, k):
    if not (c and k):
        return only(c, k, c and c["type"], k and k["type"])
    ct, kt = c["type"], k["type"]
    if not kt:
        return fld(ct, kt, ct, "crm", "only", "calendar can't tell the type")
    if not ct:
        return fld(ct, kt, kt, "cal", "filled", "crm has no type", "calendar type is a guess")
    if ct == kt:
        return fld(ct, kt, ct, "both", "same")
    # type and location are decided together, both from the calendar
    return fld(ct, kt, kt, "cal", "conflict", "calendar wins, needs a human check",
               "calendar type is a guess from location and people")


def f_status(c, k):
    if not (c and k):
        return only(c, k, c and c["status"], k and k["status"])
    cs, ks = c["status"], k["status"]
    if c["group"] == k["group"]:
        if (cs or "").lower() == (ks or "").lower():
            return fld(cs, ks, cs, "both", "same")
        return fld(cs, ks, cs, "crm", "diff", "crm wording is shown", "different words, same meaning")
    # a cancel wins: showing a dead meeting as alive is the worse mistake
    if c["group"] == "cancelled":
        return fld(cs, ks, cs, "crm", "conflict", "cancelled wins", "calendar may be out of date")
    if k["group"] == "cancelled":
        return fld(cs, ks, ks, "cal", "conflict", "cancelled wins", "crm may be out of date")
    return fld(cs, ks, ks, "cal", "conflict", "calendar wins", "confirmed vs tentative")


def f_loc(c, k):
    if not (c and k):
        return only(c, k, c and c["loc"], k and k["loc"])
    cl, kl = c["loc"], k["loc"]
    rel = loc_rel(cl, kl)
    if rel == "missing":
        show = cl or kl
        if not show:
            return fld(cl, kl, None, None, "empty", "no value")
        return fld(cl, kl, show, "crm" if cl else "cal", "filled", "one source has it")
    if rel == "same":
        return fld(cl, kl, cl, "both", "same")
    if rel in ("more detail", "similar"):
        # show the longer one, a tie goes to the calendar
        use_cal = len(words(kl)) >= len(words(cl))
        return fld(cl, kl, kl if use_cal else cl, "cal" if use_cal else "crm", "diff",
                   "more detailed wording is shown", "same place, different detail")
    return fld(cl, kl, kl, "cal", "conflict", "calendar wins, needs a human check", "different places")


def f_owner(c, k):
    if not (c and k):
        return only(c, k, c and c["owner"], k and k["owner"])
    # crm has a name, calendar has an email
    name = words(c["owner"])
    mail = squash((k["owner"] or "").split("@")[0])
    if name and all(w in mail for w in name):
        return fld(c["owner"], k["owner"], c["owner"], "both", "same")
    return fld(c["owner"], k["owner"], c["owner"], "crm", "diff", "crm owner is shown",
               "organizer is someone else, maybe a coordinator")


def f_client(c, k):
    val = None
    if c and (c["client"] or c["company"]):
        val = " - ".join(x for x in (c["client"], c["company"]) if x)
    return only(c, None, val, None)


def f_people(c, k):
    return only(None, k, None, k and k["people"])


def f_notes(c, k):
    cn, kn = c and c["notes"], k and k["notes"]
    if cn and kn:
        return fld(cn, kn, cn, "crm", "info", "crm notes first, both shown")
    return only(c, k, cn, kn)


FIELDS = {"title": f_title, "start": f_start, "end": f_end, "type": f_type, "status": f_status,
          "loc": f_loc, "owner": f_owner, "client": f_client, "people": f_people, "notes": f_notes}


def meeting(c, k, m=None):
    # c or k can be None, m is the match info
    f = {name: fn(c, k) for name, fn in FIELDS.items()}
    start = f["start"]["show"]
    return {
        "id": (c or k)["id"].lower(),
        "where": "both" if (c and k) else ("crm" if c else "cal"),
        "title": f["title"]["show"],
        "start": start,
        "has_time": bool(start and "T" in start),
        "type": f["type"]["show"],
        "status": f["status"]["show"],
        "recurring": bool(k and k.get("recurring")),
        "conflicts": [n for n, x in f.items() if x["kind"] == "conflict"],
        "diffs": [n for n, x in f.items() if x["kind"] == "diff"],
        "fields": f,
        "ids": {"crm": c["id"] if c else None, "cal": k["ids"] if k else []},
        "match": {"score": m["score"], "why": m["why"]} if m else None,
        "warns": (c["warns"] if c else []) + (k["warns"] if k else []),
    }


def merge_all(pairs, crm_left, cal_left):
    out = [meeting(p["crm"], p["cal"], p) for p in pairs]
    out += [meeting(c, None) for c in crm_left]
    out += [meeting(None, k) for k in cal_left]
    # by time, a record with no date goes last
    out.sort(key=lambda m: (m["start"] is None, m["start"] or "", m["id"]))
    return out
