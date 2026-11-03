# Decision log

**(author)** = decided by the author. The rest were proposed by the AI and accepted.

| # | Decision | Why |
|---|---|---|
| 1 | **(author)** Python, FastAPI, plain HTML/CSS/JS | One process, one command, no build step |
| 2 | **(author)** New York time for everything | One zone keeps it simple. CAL-A4 becomes a 1-hour conflict (it would agree in Chicago time) |
| 3 | **(author)** Cancelled wins, and is flagged (CRM-1009) | A dead meeting shown as live is the worse mistake |
| 4 | Match by score, same day required, pair at 0.55+ | Titles rarely agree. Accepted matches score 0.85+, best rejected 0.4 |
| 5 | Time is a hint (15 / 60 / 180 min) | CRM-1016 is 2 hours apart and still the same meeting |
| 6 | Duplicates: same day, within 60 min, half the attendees shared (calendar) or same client (CRM) | Title matching merges the weekly syncs and misses A5 + A6 |
| 7 | Keep the oldest duplicate, combine attendees, keep the fuller location | Nothing is lost, and the merge is in the report |
| 8 | Field kinds: `conflict`, `diff`, `filled`, `same`, `only`, `info`, `empty` | Exact comparison gives 8 false conflicts |
| 9 | Locations compared by word overlap | "Room B" and "HQ - Room B" are the same place |
| 10 | Type and location decided together, calendar wins, flagged | Zoom and In-Person can't be mixed |
| 11 | Calendar type is a guess (link means Virtual, all `@firma.com` means Internal). Unknown is never a conflict | The calendar has no type field |
| 12 | Repair and report bad values. A row with no ID is skipped and listed | Don't lose a meeting over a typo |
| 13 | Owner mismatch is a `diff` | Owner and organizer are different things |
| 14 | Recurring instances stay separate | Different dates, each is real |
| 15 | Data kept in memory | 42 records, no database needed |
