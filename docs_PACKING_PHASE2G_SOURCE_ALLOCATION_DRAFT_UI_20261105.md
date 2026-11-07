# Packing Phase 2G — Source Allocation, DRAFT Service and UI
Date: 05-Nov-2026

## Database migration
- Verified a full custom-format PostgreSQL backup before schema work: `database/backups/ali_raza_erp_pre_packing_phase2g_20261105.dump` (974,980 bytes; `pg_restore --list` returned 1,610 entries).
- Applied `database/migrations/20261105_003_packing_source_allocations.sql` in one transaction.
- Added `production.packing_source_allocations` with typed foreign keys to either a Nalki output line or an outside-labeling return line, packing order/item linkage, company, variant, batch, location, process stage, ownership/owner, quantity and source-cost snapshot.
- Added `process_stage_id` to `production.outside_labeling_return_lines`; existing return-line count was zero, so no existing rows were backfilled or changed.
- Added database guard triggers: allocations can only be inserted/changed/deleted while the same-company packing order is DRAFT; source line must still be a POSTED accepted fresh output or accepted usable party return; source stage must be NALKI/LABELING; return must preserve source Nalki-line lineage and PARTY owner; source snapshot must match variant/batch/location/stage/ownership/cost; packing item type/ownership/quantity must match allocation.
- Guard hardening migrations 004 and 005 were applied after the base migration to enforce stage, return lineage, and packing-item consistency.

## Application implementation
- Updated read-only random source selector to require explicit process stage on outside-labeling returns, accepted statuses, source cost, active NALKI variant/brand/shade, positive matching stock and unique stock-bucket attribution.
- Added `app/packing_random_draft_service.py`: DRAFT-only persistence creates a separate packing item for each source-line allocation, then stores its typed source allocation. It locks source lines and exact stock-balance buckets, refreshes candidates inside the same transaction, and revalidates all 100 unique shades.
- Browser-supplied data can choose only source type, source-line ID and requested quantity. Variant, shade, batch, owner, stage, availability and cost are reloaded from database candidates.
- Source cost is retained as an allocation snapshot only; it is not posted to accounting or rolled into header cost. Packaging material, weight, theka labour, inventory consumption, FG transfer and posting remain outside this phase.
- Added separate `/modules/packing/random/new` GET/POST route and `packing_random.html` page with CSRF protection, body-size limit and permission `packing.create`. Added a Packing dashboard link. Existing fixed 100-shade assortment flow remains separate.
- The random draft page is intentionally disabled when no eligible source lines exist.

## Verification
- Python compilation: PASS.
- Full unit test suite: 172/172 PASS.
- Jinja templates `packing.html` and `packing_random.html`: loaded successfully.
- Random packing route registered.
- Live source selector for company 1 returned an empty list without SQL errors.
- ERP health: `app=ok`, `database=true`.
- Read-only counts after migration: 0 source allocations; 0 outside-labeling return lines; packing orders remain 2; packing items remain 4; packing status events remain 0.
- No packing draft was created. No stock, ledger, accounting, labour, approval, existing packing order/item, or posted FG transfer was changed.
- Code snapshot: `BACKUP_PACKING_PHASE2G_CODE_SNAPSHOT_20261105`.

## Remaining gate
- No live Nalki output lines or outside-labeling return lines exist yet. Therefore the random source table is empty and the UI save button remains disabled. The source allocation and DRAFT workflow are ready for real source data, but must first be exercised against real accepted production/return lines in a controlled draft-only test.
- Approval/posting must revalidate stock again. DRAFTs do not reserve stock. Inventory consumption, packaging-material issues/returns, empty regular-box returns, quality/wastage, weights, packing theka and accounting are not enabled by this phase.
