# Opening Balance Empty-Set Reconciliation Fix — 05-Nov-2026

## Approved implementation
The user explicitly approved a narrow correction to the opening-balance candidate reconciliation indicator.

## Change
- Added `_candidate_movement_is_balanced(candidate_lines, debit_total, credit_total)`.
- The indicator is now true only when at least one eligible candidate line exists AND debit total equals credit total.
- Empty candidate sets no longer report a successful balance merely because zero equals zero.
- Posting readiness remains separately blocked; this change does not approve or post opening balances.

## Regression coverage
- Empty candidate set with zero debit and credit => false.
- Non-empty candidate set with equal totals => true.
- Non-empty candidate set with unequal totals => false.

## Verification
- `tests/test_accounting_reports.py`: 35 tests passed using Python unittest discovery.
- `py_compile` passed for `app/accounting/report_service.py` and `tests/test_accounting_reports.py`.
- pytest was unavailable in the project environment; unittest was used instead.

## Safety and backup
- Backup: `BACKUP_OPENING_BALANCE_EMPTY_SET_20261105_122757`
- No database writes, schema changes, account changes, party profile changes, opening-balance changes, journal creation, or posting.
- Existing fiscal-year records and all financial data were left untouched.