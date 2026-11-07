# Ali Raza Enterprises ERP — Packing Module Phase 1
Date: 05-Nov-2026
Working copy: ARE ERP SAFE WORKING COPY CSS FIXED 18-Oct-2026

## Implemented
- Replaced the generic Packing placeholder with a dedicated Packing Orders page.
- Added GET /modules/packing/new and CSRF-protected POST /modules/packing/new.
- Added company-scoped order listing, search by packing number/status, item counts and brand summaries.
- Added a draft-only form with 1–20 Nalki variant lines, packing date, finished wall-box quantities and remarks.
- Server-side validation restricts selection to active Nalki variants with at least 100 pieces of OWN stock in the NALKI or LABELING process stages. PARTY stock and FINISHED_GOODS-stage stock are excluded. Each requested line is checked against available quantity. PARTY stock is not selectable or accepted.
- Initial Phase 1 implementation mistakenly selected core.locations code PACKING as the order location. Phase 1B corrects this: draft order location_id remains NULL; Packing is only a process stage, never a warehouse.
- Each finished wall box is 100 pieces = 10 small boxes × 10 pieces. Header planned_quantity_boxes stores finished wall boxes; item boxes_qty stores small boxes; pieces_per_box remains 10.
- Draft save inserts the packing order, item rows, DRAFT status-history row and core.audit_log entry in one database transaction.
- Draft save does not reserve/consume stock, create stock documents, transfer FG, calculate weight/cost or pay labour.
- Weight/cost remain deliberately uncalculated. Schema-required weight numeric fields are stored as zero placeholders; item unit_cost/total_cost remain NULL. No accounting entry is created.
- Packing sidebar navigation now highlights the active page. Dashboard module status changed to Draft-only workflow enabled.

## Permissions — unchanged
- Existing database grants: OWNER and PACKING_SUPERVISOR have packing.create; ERP_ADMIN, OWNER, PACKING_SUPERVISOR and AUDITOR have packing.view.
- Babar Rasheed remains ERP_ADMIN and currently has packing.view only. The New Packing Draft button is intentionally hidden for this account; no permission grants or role changes were made.
- No new user was created.

## Verified source data (read-only)
- Two active OWN Nalki variants currently have positive stock: NALKI-CHANNEL-1 (300 pieces, Finished Goods stage) and NALKI-GOLDEN_CHAIN-1 (123 pieces across Nalki, Labeling and Finished Goods stages).
- These stage names remain workflow labels within one physical godown; they are not treated as separate warehouses.
- Existing database counts before and after implementation remain: 2 packing orders, 4 packing order items, 2 labour rows, 2 POSTED FG transfer rows, 0 packing status-history rows, 0 core.audit_log rows.
- Existing packing test records and posted FG transfers were not modified.

## Verification
- Focused packing + configuration suites: 39/39 tests passed.
- Python compilation passed for packing_service.py, main.py and packing tests.
- Jinja compilation and render of both list and draft form passed.
- OpenAPI confirms GET and POST /modules/packing/new.
- Live app restarted; /health reports app=ok and database=true.
- Actual INSERT and audit SQL were exercised against PostgreSQL inside an outer transaction that was deliberately rolled back. The test returned a DRAFT result and then confirmed all four table counts were unchanged.
- No database migration or schema change was made.

## Backup and safety
- Code backup: BACKUP_PACKING_PHASE1_20261105.
- No business records, stock balances, posted documents, role grants or permissions were changed.
- Temporary verification scripts are removed after final checks.

## Next implementation gate
Implement packing approval/posting only after validating source traceability from Nalki output / outside-labeling return, empty small-box returns, packing-material consumption, Nalki-only theka labour, QC, wastage and FG transfer. Preserve the single physical godown and pin the applicable approved configuration version to each packing document. Do not alter existing POSTED FG transfers.

## Phase 1B ? Process-stage / single-godown correction
- Read-only inspection found 9 legacy core/inventory location records named Raw Material Store, Dyeing, Big Cone, Baby Cone, Nalki, Labeling, Packing, Finished Goods and Dispatch. These are legacy location records and must not be treated as the target physical warehouse design.
- New packing drafts no longer require or write the legacy PACKING location ID; production.packing_orders.location_id is left NULL because the draft does not select a physical godown.
- Eligible source balances are now selected by master.process_stages.code (NALKI or LABELING), not by core.locations.name. FINISHED_GOODS stock is excluded so already finished stock cannot be repacked accidentally.
- The form only lists variants with at least 100 OWN pieces, and server-side draft validation checks the requested piece quantity against eligible stage stock. This is a validation snapshot only; it does not reserve stock, so posting/reservation still requires a later controlled phase.
- No DB schema, business data, stock, location records, permissions, or existing POSTED FG transfers were changed.