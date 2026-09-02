# Changelog

## 0.1.1 - 2026-09-02

- Fix current stock snapshot for InvenTree custom stock statuses
- Resolve custom statuses dynamically using `StockStatus.custom_queryset()`
- Do not hard-code numeric custom status keys
- Use configured status `name` / `label` for classification
- Improve historical Rework status lookup to resolve custom keys dynamically
- Add **Print / Save PDF**
- Add **Download CSV**
- No change to FPY or test-duration calculation rules

## 0.1.0 - 2026-09-02

- Initial Part Quality Report
