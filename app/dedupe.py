from datetime import timedelta

# 30 min apart is still the same meeting (CAL-A5 / A6)
GAP = timedelta(minutes=60)


def is_dup(a, b):
    # caller passes records of one source only, each source has its own rule below
    if not a["start"] or not b["start"]:
        return False
    if a["start"].date() != b["start"].date():
        return False
    # CRM time can be missing, midnight is fake so skip the check
    if a["has_time"] and b["has_time"] and abs(a["start"] - b["start"]) > GAP:
        return False

    if a["src"] == "crm":
        # no attendees in CRM, same client on same day is the best we have
        return bool(a["client"] and a["client"] == b["client"] and a["company"] == b["company"])

    # calendar: most of the people overlap. ratio, so a longer invite list still counts
    x = {p for p in a["people"] if "@" in p}
    y = {p for p in b["people"] if "@" in p}
    return bool(x and y and len(x & y) / len(x | y) >= 0.5)


def merge(g):
    # oldest record is the original, others are copies
    g = sorted(g, key=lambda r: r["created"].timestamp() if r["created"] else float("inf"))
    main = dict(g[0])
    main["ids"] = [r["id"] for r in g]
    if len(g) == 1:
        return main

    # keep everyone, no one is lost
    main["people"] = list(dict.fromkeys(p for r in g for p in r["people"]))
    # longest location is the most detailed one
    locs = [r["loc"] for r in g if r["loc"]]
    main["loc"] = max(locs, key=len) if locs else None
    main["warns"] = [w for r in g for w in r["warns"]] + ["merged " + ", ".join(main["ids"][1:])]
    return main


def dedupe(recs):
    # simple grouping, fine for this data size
    groups = []
    for r in recs:
        for g in groups:
            if any(is_dup(r, x) for x in g):
                g.append(r)
                break
        else:
            groups.append([r])

    out, dups = [], []
    for g in groups:
        m = merge(g)
        out.append(m)
        if len(g) > 1:
            # for the report
            dups.append({"src": m["src"], "kept": m["ids"][0], "dropped": m["ids"][1:]})
    return out, dups
