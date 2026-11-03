from .dedupe import dedupe
from .match import THRESH, match
from .merge import merge_all
from .normalize import TZ, load_all, warn_list


def build(folder):
    # whole pipeline: load -> dedupe -> match -> merge
    d = load_all(folder)
    crm, crm_dups = dedupe(d["crm"])
    cal, cal_dups = dedupe(d["cal"])
    pairs, crm_left, cal_left = match(crm, cal)
    meetings = merge_all(pairs, crm_left, cal_left)

    # warnings come from the raw records so each one keeps its own id
    warns = warn_list(d["crm"] + d["cal"])
    where = [m["where"] for m in meetings]
    report = {
        "timezone": TZ.key,
        "threshold": THRESH,
        "counts": {
            "crm_rows": len(d["crm"]),
            "cal_rows": len(d["cal"]),
            "crm_after_dedupe": len(crm),
            "cal_after_dedupe": len(cal),
            "meetings": len(meetings),
            "both": where.count("both"),
            "crm_only": where.count("crm"),
            "cal_only": where.count("cal"),
            "conflicts": sum(1 for m in meetings if m["conflicts"]),
            "warns": len(warns),
        },
        "dups": crm_dups + cal_dups,
        "warns": warns,
        "skipped": d["skipped"],
    }
    return {"meetings": meetings, "report": report}
