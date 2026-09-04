# InvenTree Part Quality Report

Version **0.1.3**

A lightweight on-demand quality report for a single InvenTree Part.

## Report sections

1. **Current Stock Snapshot** — Pass VI, Pass BU, Pass SW, Failed VI, Failed BU, Failed SW, Rework, Other.
2. **First Pass Yield (FPY)** — first recorded attempt per stock item / test determines FPY. Later passes do not repair FPY.
3. **Test Duration** — timed-result count, excluded count, median, minimum and maximum from `finished_datetime - started_datetime`. Missing, zero and negative durations are excluded. Retests count as timing observations.
4. **Rework Rate** — hybrid detection from current / historical Rework status and Rework test results.

## v0.1.3 changes

- Replaces arithmetic average test duration with **median**.
- Minimum and maximum duration values can be selected in the report.
- Selecting Min or Max shows the exact underlying Test Result ID(s), Stock Item / serial, start time, finish time and duration.
- All tied min / max records are shown.
- CSV export includes median duration plus the min / max Test Result IDs and a detailed min / max record section.
- Uses a new frontend asset filename (`quality_report_v013.js`) to force a fresh UI load after upgrade.

## Existing behavior retained

- Current Stock Snapshot count and percentage
- First Pass Yield based on first recorded attempt
- Missing / zero / negative duration exclusion
- Dynamic custom stock-status resolution
- Hybrid rework detection
- Print / Save PDF
- Download CSV
