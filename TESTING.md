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
