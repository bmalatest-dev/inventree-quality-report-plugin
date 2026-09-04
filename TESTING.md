# Local test plan — v0.1.3

## Timing median

Create five valid timed results for the same test:

- 5 minutes
- 10 minutes
- 15 minutes
- 20 minutes
- 120 minutes

Expected:

- Median = 15 minutes
- Min = 5 minutes
- Max = 120 minutes

This specifically confirms that the long 120-minute result does not distort the representative duration as an arithmetic average would.

## Even-number median

Create four valid results:

- 5 minutes
- 10 minutes
- 20 minutes
- 30 minutes

Expected median = 15 minutes.

## Exclusion

Add:
- one zero-duration result
- one negative-duration result
- one missing-start result
- one missing-finish result

All must increment Excluded and must not affect Median / Min / Max.

## Min / Max record selection

Select Min.

Expected:
- exact Stock Item ID
- serial when populated
- Test Result ID
- duration
- started timestamp
- finished timestamp

Select Min again and confirm details collapse.

Repeat for Max.

## Ties

Create two results with the same minimum duration and two with the same maximum duration.

Expected:
- selecting Min shows both minimum records
- selecting Max shows both maximum records

## CSV

Download CSV.

Expected:
- timing header uses `Median Seconds`, not Average
- Min Result IDs are included
- Max Result IDs are included
- detailed Min / Max record section is included

## Regression

Confirm:
- Current Stock Snapshot unchanged
- FPY unchanged
- Rework unchanged
- Print / Save PDF still works
- Download CSV still works
