# Local test plan — v0.1.0

Use dummy data in the local instance.

## FPY cases

- A: VI PASS, BU PASS, SW PASS → all FPY pass.
- B: VI FAIL, VI PASS, BU PASS, SW PASS → VI FPY fail; BU/SW pass.
- C: VI PASS, BU FAIL, BU PASS, SW PASS → BU FPY fail.

## Timing

Create three VI results:
- 5 minutes
- 10 minutes
- 15 minutes

Expected average 10m, min 5m, max 15m.

Add one zero-duration result and one result with a missing timestamp. Both must increment Excluded and must not affect average/min/max.

## Rework

- Test-only: record Rework test result, no tracked Rework status → Rework Test Only +1.
- Tracking-only: set status to Rework then move out, no Rework test → Stock Tracking Only +1.
- Both: use both signals → Found in Both +1, but Unique Stock Items Reworked only +1.

## Snapshot

Place dummy stock items into Pass VI, Pass BU, Pass SW, Failed VI, Failed BU, Failed SW and Rework. Confirm current counts match exactly.


## v0.1.1 custom status test

Assign arbitrary custom numeric keys to statuses such as `PASS_VI`, `PASS_BU`, or `REWORK`.
The report must classify by configured status name / label, not by numeric key.

## v0.1.1 export test

After loading the Quality Report:

1. Click **Print / Save PDF** and verify all four sections appear.
2. Save as PDF using the browser print dialog.
3. Click **Download CSV** and verify snapshot, FPY, timing, and rework sections are present.


## v0.1.2 Rework union test

Create two different stock items:

- Item A: currently in custom status `Rework`, with no Rework test
- Item B: has a Rework test result, but is not currently in Rework status

Expected:

```text
Status / Tracking Only: 1
Rework Test Only:       1
Found in Both:          0
Unique Reworked:        2
```

If there are 5 total stock items, expected Rework Rate is 40.0%.

## v0.1.2 Snapshot percentage test

With 5 total stock items and one currently in Pass VI:

```text
Pass VI  1  20.0%
```

The Total row must show 100.0%.
