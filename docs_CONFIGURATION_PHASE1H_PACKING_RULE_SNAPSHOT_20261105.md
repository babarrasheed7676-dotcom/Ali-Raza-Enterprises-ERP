# Configuration Phase 1H — Immutable Rule Snapshot Integration for Nalki Packing

**Date:** 05-Nov-2026  
**Status:** First operational configuration consumer integrated in SAFE WORKING COPY.

## Scope
The first live consumer of the governed Configuration register is Nalki Packing. All three DRAFT creation paths now resolve and attach the applicable Nalki finished-wall-box packaging rule:
1. Fixed 100-shade, same-brand assortment.
2. Random 100-piece workflow with fresh and accepted usable-return sources.
3. Legacy generic packing draft service, retained behind its existing service/API boundary.

## Rule identity and business semantics
- Configuration type: `PACKAGING_RULE`
- Configuration key: `NALKI-FINISHED-WALL-BOX`
- Finished wall box: exactly 100 Nalki pieces.
- Inner regular box: `PACK_BOX-STD`, exactly 10 pieces.
- One finished wall box contains 10 regular boxes.
- The finished 100-piece wall box remains a distinct finished-product pack; `PACK_BOX-STD` is never reinterpreted as the finished wall box.
- This phase does not infer any per-piece weight or create material/stock movements.

## Runtime resolution
- Resolve only an APPROVED version for the same company, exact type/key and packing date within effective_from/effective_to.
- Lock the selected version row `FOR SHARE` during the DRAFT transaction.
- More than one effective approved match is a hard error.
- An approved but malformed/incompatible rule is a hard error; no silent fallback.
- If no approved version exists, pin an explicit `SYSTEM_DEFAULT` baseline snapshot with the same validated 100/10 relationship. This is not represented as an approved Configuration version.
- The resolved payload and source/version identity are attached in the same transaction as the packing DRAFT.

## Database protection
Migration `20261105_006_packing_configuration_snapshots.sql` adds `production.packing_configuration_snapshots`.
Migration `20261105_007_packing_configuration_snapshot_guard.sql` hardens the trigger:
- Only the exact Nalki packaging rule identity is accepted.
- Snapshot must match the parent DRAFT order's company, creator and packing date.
- APPROVED_VERSION snapshots must reference an APPROVED, effective, same-company/type/key version and exactly match its payload.
- SYSTEM_DEFAULT snapshots must match the database-guarded baseline values (100 pieces, 10 regular boxes, PACK_BOX-STD, Nalki, PCS).
- UPDATE and DELETE are rejected; one snapshot per order/type/key.
- Snapshot row can only be inserted while the parent packing order remains DRAFT.

## Tests and live verification
- Configuration + packing focused suites passed.
- Full application suite: **195/195 passed**.
- Python compilation passed.
- Application restarted; health returned `{"app":"ok","database":true}`.
- Packing page list query returned both existing orders and displayed “Not available” where no snapshot exists; no old order was backfilled.
- Database rollback probe inserted a temporary DRAFT and matching SYSTEM_DEFAULT snapshot, verified snapshot readback, verified UPDATE rejection, and verified tampered default payload rejection. The outer transaction was deliberately rolled back.
- Post-rollback snapshot row count: **0**.
- No real packing order, configuration version, inventory, stock ledger, FG transfer, labour row, accounting entry, master data, role or permission was created/changed by this phase.

## Backups and files
- Database pre-migration backup: `database/backups/ali_raza_erp_pre_packing_config_snapshot_20261105.dump`
- Additional pre-guard backup: `database/backups/ali_raza_erp_pre_packing_snapshot_guard_20261105.dump`
- Code snapshot: `BACKUP_PACKING_CONFIG_VERSION_PINNING_20261105_224033`
- Migration 006: `database/migrations/20261105_006_packing_configuration_snapshots.sql`
- Migration 007: `database/migrations/20261105_007_packing_configuration_snapshot_guard.sql`
- Runtime resolver: `app/configuration_runtime_service.py`
- Tests: `tests/test_configuration_runtime_service.py`

## Remaining Configuration integration
This is the first consumer, not blanket completion of all operational adoption. Remaining rule families need separate adapters and snapshots:
- Product/Item and Unit definitions → master/item setup and Purchasing.
- Unit conversions and measurement profiles → inventory, production and costing.
- Baby Cone measurement and process routes → Baby Cone / Nalki production as applicable.
- Ownership policy → OWN/PARTY source and issue validation; PARTY Nalki remains disabled until owner/request/approval/locked-rate policy is approved.
- Process cost rules → production and outside-labeling cost capture without double counting.
- Approval policy → operational maker-checker gates only after role mapping and separation-of-duties review.

Do not create an APPROVED version or mutate a master record merely to demonstrate this integration. No factory deployment or posting is included.

**Completion boundary:** Nalki Packing now pins a validated immutable packaging-rule snapshot to each new DRAFT order. Existing orders remain unchanged; operational posting and other rule-family integrations remain future phases.
