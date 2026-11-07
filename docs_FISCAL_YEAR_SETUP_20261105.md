# Ali Raza Enterprises ERP — Fiscal Year Setup Checkpoint
## 5 November 2026

### Approved business policy
- Financial year starts on **1 July** and ends on **30 June** of the following calendar year.
- Example: FY 2026-27 = 1 July 2026 through 30 June 2027.
- Exactly 12 contiguous monthly accounting periods are generated.
- February uses the calendar month length, including 29 February in leap years.

### Implementation completed in the safe working copy
- Added `app/accounting/fiscal_year_service.py`.
- Added a July-to-June fiscal-year definition builder and twelve-period generator.
- Added an atomic create service for the existing `core.fiscal_years` and `core.accounting_periods` tables.
- Creation checks for same-company date overlaps and serializes creation with a PostgreSQL transaction advisory lock.
- The existing fiscal-year table has no attached ID sequence/default; the service allocates the next ID under the global advisory lock.
- Twelve accounting periods and one audit-log entry are written in the same transaction.
- Added POST route `/accounting/fiscal-year/create`, protected by `accounting.approve` and the existing double-submit CSRF validation.
- Updated the Fiscal Year Setup page to default to the current July-June year, preview before writing, and show a separate create action only for a valid full-year range and users with approval permission.
- No opening balance, journal, stock, or other financial transaction is created by this workflow.

### Verification
- New fiscal-year service tests: 4 passed.
- Existing fiscal-period preview tests: 3 passed.
- Python compilation: successful.
- FastAPI application import: successful; fiscal-year create route registered.
- Jinja template load: successful.
- Database verification ran in a READ ONLY transaction:
  - Company 1 fiscal years: 0.
  - Company 1 accounting periods: 0.

### Safety and remaining hardening
- No live fiscal year or accounting period was created.
- No database schema migration was applied.
- Existing tables and constraints were reused.
- Overlap prevention is enforced by the application service's advisory-lock transaction. Direct manual SQL inserts that bypass this service would not take that lock; a future database exclusion constraint migration should be separately reviewed before production use.
- The current FY 2026-27 is previewable. An authorized accounting approver must explicitly submit the separate create action to create it.
- Opening Balance Clearing account policy remains unapproved and untouched.

### Backup
`BACKUP_FISCAL_YEAR_SETUP_20261105` contains pre-change copies of:
- `app/main.py`
- `app/templates/fiscal_period_preview.html`
- `app/accounting/report_service.py`
- `tests/test_accounting_reports.py`
