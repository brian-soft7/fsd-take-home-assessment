import re

# score needed to call two records the same meeting
THRESH = 0.55

# words that don't point to one company
GENERIC = {"capital", "partners", "group", "advisors", "holdings", "ventures",
           "wealth", "investments", "institutional", "investors", "fund", "vii"}
STOP = {"the", "and", "with", "a", "of", "for", "to", "in"}
# short names that only one system uses
ALIAS = {"qbr": "quarterly business review", "lpac": "lp advisory committee", "dd": "due diligence"}


def words(s):
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def squash(s):
    # "david.park@x.com" -> "davidparkxcom", easy to search in
    return re.sub(r"[^a-z0-9]", "", s.lower())


def title_words(s):
    out = set()
    for w in words(s):
        if w not in STOP:
            out.update(ALIAS.get(w, w).split())
    return out


def loc_words(s):
    # zoom links are noise
    return set(words(re.sub(r"https?://\S+", " ", s or "")))


def loc_rel(a, b):
    # same / more detail / similar / different / missing
    x, y = loc_words(a), loc_words(b)
    if not x or not y:
        return "missing"
    if x == y:
        return "same"
    # "Room B" vs "HQ - Room B" is the same place
    if x <= y or y <= x:
        return "more detail"
    if len(x & y) / len(x | y) >= 0.4:
        return "similar"
    return "different"


def score(c, k):
    # c = crm record, k = calendar record. returns (score, reasons)
    # different day is never the same meeting, even for the same client
    if not c["start"] or not k["start"] or c["start"].date() != k["start"].date():
        return 0, []
    s, why = 0, ["same day"]

    if c["has_time"]:
        gap = abs((c["start"] - k["start"]).total_seconds()) / 60
        # time is a hint only, CRM-1016 is 2 hours off and still the same meeting
        for limit, pts in ((15, 0.4), (60, 0.3), (180, 0.15)):
            if gap <= limit:
                s += pts
                why.append("start %d min apart" % gap)
                break
    else:
        s += 0.1
        why.append("crm has no time")

    # who: look for company / client / owner inside title, notes and emails
    hay = squash(" ".join([k["title"] or "", k["notes"] or "", k["owner"] or ""] + k["people"]))
    comp = [w for w in words(c["company"]) if w not in GENERIC and len(w) > 2]
    if any(w in hay for w in comp):
        s += 0.35
        why.append("company %s found" % c["company"])
    name = words(c["client"])
    if name and all(w in hay for w in name):
        s += 0.15
        why.append("client %s is attending" % c["client"])
    owner = words(c["owner"])
    if owner and all(w in hay for w in owner):
        s += 0.1
        why.append("owner is organizer or attendee")

    # what and where
    a, b = title_words(c["title"]), title_words(k["title"])
    if a & b:
        s += 0.25 * min(1, len(a & b) / min(len(a), len(b)) * 1.5)
        why.append("title words: " + ", ".join(sorted(a & b)))
    if loc_rel(c["loc"], k["loc"]) in ("same", "more detail", "similar"):
        s += 0.1
        why.append("location agrees")
    return round(s, 2), why


def match(crm, cal):
    cands = []
    for c in crm:
        for k in cal:
            s, why = score(c, k)
            if s >= THRESH:
                cands.append((s, c, k, why))
    # best score first, so a weak pair can't steal a record from a strong one
    cands.sort(key=lambda x: -x[0])

    used_c, used_k, pairs = set(), set(), []
    for s, c, k, why in cands:
        if c["id"] in used_c or k["id"] in used_k:
            continue
        used_c.add(c["id"])
        used_k.add(k["id"])
        pairs.append({"crm": c, "cal": k, "score": s, "why": why})

    crm_left = [c for c in crm if c["id"] not in used_c]
    cal_left = [k for k in cal if k["id"] not in used_k]
    return pairs, crm_left, cal_left
