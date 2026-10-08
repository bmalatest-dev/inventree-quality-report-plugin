# Changelog

## 0.2.0 - 2026-10-08

- Fix plugin discovery for the new AppMixin-backed timing model.
- Defer `TestTimingCapture` model import until after InvenTree has registered the plugin package as a Django application.
- Retain immutable tested-quantity capture, split-history deduplication, units-processed and total-test-time metrics from v0.1.8/v0.1.9.
- Add versioned frontend asset `quality_report_v020.js`.

## 0.1.9

- Removed the top-level dependency on `InvenTree.helpers.generateTestKey`.
- Uses the canonical `rework` test key directly for the Rework test, avoiding plugin discovery/import failures when the InvenTree backend package is not on the plain Python import path.
- Retains all v0.1.8 immutable tested-quantity and production-effort reporting changes.

## 0.1.8 - 2026-10-08

- Capture tested quantity immutably when each new StockItem test result is created.
- Calculate historical time/unit from captured tested quantity, never current StockItem quantity.
- Deduplicate copied test-history rows created by later StockItem splits so copied history does not become new production effort.
- Count genuine retests as additional units processed and additional test time.
- Add Total Test Time to the Test Duration section and CSV export.
- Explicitly exclude legacy timing records which pre-date quantity capture rather than presenting unreliable time/unit values.
- Preserve existing FPY behavior.


## 0.1.3 - 2026-09-04

- Replace average test duration with median
- Make Min / Max timing values selectable
- Show underlying Stock Item, serial, Test Result ID, start, finish and duration
- Show all tied Min / Max results
- Add min / max record identifiers to CSV
- Rename frontend asset to force static refresh

## 0.1.2 - 2026-09-02

- Add percentage column to Current Stock Snapshot
- Count current custom `Rework` status as definitive rework evidence
- Continue to use historical Stock Tracking and Rework test results
- Rework rate is the unique union of status/tracking evidence and Rework test evidence
- Broaden historical tracking-field detection for custom / legacy status payloads
- Rename the frontend static asset to force a fresh UI load after plugin update
- Retain Print / Save PDF and Download CSV controls from v0.1.1

## 0.1.1 - 2026-09-02

- Dynamic custom stock status resolution
- Print / Save PDF
- Download CSV

## 0.1.0 - 2026-09-02

- Initial Part Quality Report
