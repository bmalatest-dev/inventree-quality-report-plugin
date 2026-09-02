# InvenTree Part Quality Report

Version **0.1.0**

A lightweight on-demand quality report for a single InvenTree Part.

## Report sections

1. **Current Stock Snapshot** — Pass VI, Pass BU, Pass SW, Failed VI, Failed BU, Failed SW, Rework, Other.
2. **First Pass Yield (FPY)** — first recorded attempt per stock item / test determines FPY. Later passes do not repair FPY.
3. **Test Duration** — count, excluded count, average, minimum and maximum from `finished_datetime - started_datetime`. Missing, zero, and negative durations are excluded. Retests count as timing observations.
4. **Rework Rate** — hybrid detection: historical transition into Rework status OR a Rework test result. If both exist, the stock item counts once.

## Design

- Part-page UI panel named **Quality Report**
- Calculated on demand
- Exact selected Part only; variants are not included automatically
- Counts StockItem records rather than stock quantity
- No database tables, migrations, scheduler, background worker, polling, or analytics database

## API action

`POST /api/action/`

```json
{
  "action": "part_quality_report",
  "data": {"part": 1}
}
```

## Current assumptions

- Primarily intended for serialized / trackable PCBAs.
- Custom stock status labels are normalized so names such as `PASS_VI` and `Pass VI` map to the same bucket.
- Rework test detection expects a test template whose normalized key is `rework`.
