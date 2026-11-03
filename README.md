# Event Sync Service

Pulls meetings from a **CRM** export and a **Calendar** export, finds the ones that are the same meeting, merges them, and shows one list. The page shows **where each value came from** and **where the sources disagree**.

## Run

Needs Python 3.10+.

```bash
python run.py
```

Open http://127.0.0.1:8000 and keep the terminal open (Ctrl+C stops it). The first run creates `.venv` and installs the requirements. Use `PORT=8001` to change the port. API docs are at `/docs`.

Tests (74):

```bash
.venv\Scripts\python -m unittest        # Windows
.venv/bin/python -m unittest            # macOS / Linux
```

## Result

- **24 meetings:** 17 in both, 3 CRM only, 4 calendar only
- **1 duplicate merged:** CAL-A5 + CAL-A6
- **11 data warnings:** each repaired value, with its record
- **4 conflicts:**

| Meeting | Field | CRM | Calendar | Shown |
|---|---|---|---|---|
| CRM-1002 | type, location | In-Person, NYC Office | Zoom | Calendar |
| CRM-1004 | start | 14:00 | 15:00 | Calendar |
| CRM-1009 | status | Cancelled | confirmed | Cancelled |
| CRM-1016 | start | 13:00 | 15:00 | Calendar |

On the page, click a row to see **CRM said / Calendar said / Shown / Source** for every field.

## API

| Endpoint | What it does |
|---|---|
| `GET /api/meetings` | List. Filters: `where=both\|crm\|cal`, `conflict=true\|false`, `q=text` |
| `GET /api/meetings/{id}` | One meeting, e.g. `crm-1002` |
| `GET /api/report` | Counts, duplicates, warnings |
| `POST /api/sync` | Re-read the JSON files |

Each field has `crm`, `cal`, `show`, `src` and a `kind`: `same`, `only`, `filled`, `info`, `diff` (same fact, different words) or `conflict`.

## How it works

```
JSON files -> normalize -> dedupe -> match -> merge -> API + page
```

| Step | File | Job |
|---|---|---|
| Normalize | [normalize.py](app/normalize.py) | Clean each row, fix bad values, warn about each fix |
| Dedupe | [dedupe.py](app/dedupe.py) | Merge duplicates inside one source |
| Match | [match.py](app/match.py) | Pair CRM and calendar records by a score (same day required, pair at 0.55 or more) |
| Merge | [merge.py](app/merge.py) | Decide each field and flag conflicts |

## Data problems and what happens

| Problem | Handling |
|---|---|
| No shared ID | Score from time, company, people, title, location |
| Times differ | Time is a hint, so CRM-1016 (2 hours apart) still matches |
| `19:00Z` vs `14:00` | All times are New York time |
| Conflicting fields | Flagged, with the rule used |
| Same fact, different words | `diff`, not a conflict |
| Duplicate in one source | Merged and listed in the report |
| Missing time (CRM-1007) | Filled from the calendar |
| Bad values (`03-15/2025`, `[at]` email, "Multiple") | Repaired or ignored, with a warning |

## Key decisions

- **New York time for everything.** This makes CAL-A4 a 1-hour conflict.
- **Cancelled wins.** Showing a dead meeting as live is the worse mistake.
- **Repair and report.** Nothing is silently fixed or dropped.
- **In-memory data.** Only 42 records, so no database.

More in [docs/decision-log.md](docs/decision-log.md).

## Known limits

- The page was tested with scripts, not by eye. Layout is untested.
- A meeting moved to another day shows as two meetings.
- The calendar's meeting type is a guess from location and attendees.
- Thresholds are tuned on these 42 records only.
- No login, saved data or paging.

## More

- [docs/data-analysis.md](docs/data-analysis.md) - every record pairing
- [docs/decision-log.md](docs/decision-log.md) - decisions and why
