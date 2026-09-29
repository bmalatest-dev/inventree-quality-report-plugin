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


## v0.1.4

Quality metrics are quantity-weighted: Current Stock Snapshot, First Pass Yield, and Rework Rate use StockItem quantity rather than treating every StockItem as one unit. FPY still uses the first recorded attempt for each stock item.


## v0.1.5

Test Duration now reports tested quantity separately from test runs. Rework display uses quantity for both reworked and total quantities.


## v0.1.6

Fix the on-screen Rework Rate denominator to display Total Quantity rather than Total Stock Items.


## v0.1.7

Test Duration is expressed as effective time per unit. Each test result is assumed to represent testing the entire current stock-item lot: effective time/unit = run duration / lot quantity. Median, minimum, and maximum are calculated from the effective per-unit values for valid runs.
