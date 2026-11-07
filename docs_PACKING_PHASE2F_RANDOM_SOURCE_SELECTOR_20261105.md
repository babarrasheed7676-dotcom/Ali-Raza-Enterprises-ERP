# Packing Phase 2F — Random Source Selector Groundwork
Date: 05-Nov-2026

## Scope delivered
- Added `app/packing_random_source_service.py` as a read-only candidate selector for random 100-piece Nalki packing.
- Company-scoped candidate query accepts only posted Nalki production orders with GOOD output and ACCEPTED quality, or posted/returned outside-labeling orders with ACCEPTED return and quality status.
- Candidates must resolve to active NALKI item variants, active brand/shade masters, positive stock balance, and matching batch/location/process-stage/ownership/owner dimensions.
- Fresh production source is eligible only at the NALKI or LABELING process stage. Finished goods are not eligible.
- The query excludes ambiguous stock buckets when more than one source line shares the same variant/batch/location/stage/ownership/owner signature. It does not falsely attribute pooled stock to a particular source line.
- Added focused tests in `tests/test_packing_random_source_service.py`.

## Schema findings / fail-closed restrictions
- `production.packing_order_items` has no source-line ID or source-table reference. Existing header-level source order IDs cannot retain multiple source allocations per shade. Random packing draft persistence is therefore NOT connected.
- `production.outside_labeling_return_lines` has no `process_stage_id`. Its return source cannot safely be assumed to be at NALKI or LABELING. The selector currently fails closed for these rows unless a stock-balance row can match the NULL stage exactly; it does not infer a stage from location name.
- Source-line tables do not have a direct foreign key to the stock-balance row or stock document line. Where multiple source lines share the same stock bucket, the selector suppresses candidates rather than assigning pooled stock to one line.
- A future safe implementation needs explicit source-allocation persistence (two typed source FKs or a normalized source registry), plus a verified stage/stock-document linkage for outside-labeling returns. Availability must be revalidated under lock at approval/posting; DRAFTs do not reserve stock.

## Verification
- Python compileall for app/tests: PASS.
- Focused tests: 14/14 PASS (4 selector tests + 10 random validation tests).
- Live read-only selector call for company 1: returned an empty list, no SQL error. Existing introspection showed zero Nalki output lines and zero outside-labeling return lines.
- No route/UI, database schema, database records, stock, ledger, accounting, labour, permissions, approvals, or posting workflow changed.
- Backup: `BACKUP_PACKING_PHASE2F_SOURCE_SELECTOR_20261105`.

## Next safe step
Design and review the normalized packing-source-allocation table and exact source-to-stock traceability, then implement draft persistence only after that storage model is verified. Keep random packing hidden/disabled in operational UI until source-line traceability is complete.