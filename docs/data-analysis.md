# Data analysis

Read by hand before any code. The tests check these findings. All times are New York time.

**20 CRM + 22 calendar records = 24 meetings** (17 in both, 3 CRM only, 4 calendar only).

## Pairs

| CRM | Calendar | Note |
|---|---|---|
| 1001 | A1 | Location wording differs |
| 1002 | A2 | **Conflict:** In-Person vs Zoom |
| 1004 | A4 | **Conflict:** `19:00Z` = 15:00, CRM says 14:00 |
| 1005 | A5 + A6 | A5 and A6 are a **duplicate** (11:00 and 11:30) |
| 1006 | A7 | Internal, recurring |
| 1007 | A8 | CRM has no time, calendar fills it |
| 1008 | A9 | Bad date `03-15/2025` |
| 1009 | A10 | **Conflict:** Cancelled vs confirmed |
| 1011 | A12 | Location wording differs |
| 1012 | A13 | Agree |
| 1013 | A14 | Different titles and owner |
| 1014 | A15 | Calendar has no location |
| 1015 | A16 | Bad email `[at]` |
| 1016 | A17 | **Conflict:** 13:00 vs 15:00 |
| 1017 | A20 | Client "Multiple", attendee `external-guests` |
| 1018 | A21 | Agree |
| 1019 | A22 | No shared title words |

**CRM only:** 1003, 1010 (empty notes), 1020
**Calendar only:** A3, A18 (weekly sync, two dates), A11 (sparse), A19

## Traps

- Matching on client alone merges the same client on different days.
- Matching on date alone pairs wrong meetings on busy days.
- Matching on title would merge the two weekly syncs and miss A5 + A6.
- Exact text comparison gives 8 false conflicts (5 locations, 2 statuses, 1 owner).
- A guessed type for entries with no location (A11, A15) would be invented.
