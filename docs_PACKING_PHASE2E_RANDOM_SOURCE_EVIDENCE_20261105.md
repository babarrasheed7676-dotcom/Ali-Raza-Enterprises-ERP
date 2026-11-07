# Packing Phase 2E — Random source evidence hardening
Date: 05-Nov-2026

## Scope
Hardened pure validation in `app/packing_random_service.py`. No routes, database schema, records, inventory, permissions, or posting workflows were changed.

## Confirmed source lineage from existing schema
- Fresh Nalki source is allow-listed to `production.nalki_output_lines`; eligible evidence requires `output_type=GOOD` and `quality_status=ACCEPTED`.
- Party-rejected-but-usable source is allow-listed to `production.outside_labeling_return_lines`; eligible evidence requires both `return_status=ACCEPTED` and `quality_status=ACCEPTED`, a retained `source_nalki_line_id`, PARTY ownership, and a retained owner party.
- The allocation validator now requires explicit database-derived `stock_verified=True`; a caller-supplied usability flag alone is no longer accepted.
- Original source table, source line, batch, ownership, owner party, and unit cost are retained in normalized allocation data. Existing source cost is carried forward, not recalculated.

## Read-only live database findings
- `production.nalki_orders`: no rows.
- `production.nalki_output_lines`: no rows.
- `production.outside_labeling_orders`: no rows.
- `production.outside_labeling_return_lines`: no rows.
Therefore no actual live production/labeling source line can yet be selected or tested end-to-end. Random packing remains validation-only and is not connected to draft creation or stock posting.

## Backup
`BACKUP_PACKING_PHASE2E_SOURCE_EVIDENCE_20261105_214828`

## Verification
- Python compileall: passed.
- Full unittest discovery: 163 tests passed.
- The initial test run had one assertion-regex mismatch; corrected and the complete suite then passed.
- Database inspection ran in a READ ONLY transaction.
- No database or inventory mutations; no posting, reservation, costing write, labour, QC, or wastage records created.

## Next implementation gate
When actual source records exist, implement read-only source selectors that join production line evidence to current eligible process-stage stock by variant, batch, ownership and owner party. Then wire random packing DRAFT creation with per-source allocation rows only after confirming the existing schema can retain every source-line identity. Do not infer usability from stock presence alone.
