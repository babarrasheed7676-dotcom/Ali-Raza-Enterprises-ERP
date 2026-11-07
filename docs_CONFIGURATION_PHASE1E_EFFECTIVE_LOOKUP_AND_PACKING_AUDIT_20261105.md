# Configuration Phase 1E — Effective Rule Resolver & Packing Readiness Audit
Date: 05-Nov-2026

## Effective configuration resolver
- Added a company-scoped, read-only service lookup for one APPROVED configuration version by type, key, and effective date.
- Added GET /configuration/api/effective with configuration.history.view permission (ERP_ADMIN-only under the current role assignment).
- The resolver returns no configuration when none is effective and fails closed if more than one APPROVED version matches.
- No configuration row is created or changed by this lookup.
- Tests cover exactly one match, no match, and duplicate-match integrity failure.

## Verification
- Configuration service and rule tests: 32/32 passed.
- Python compilation passed; application import and configuration template load passed.
- New effective lookup route appears in the live OpenAPI document after restarting the local server.
- Live ERP health after restart: {"app":"ok","database":true}.
- A read-only lookup for a non-existent probe key returned None.
- No database writes were made.

## Packing module readiness audit
- The /modules/packing page currently uses the generic module placeholder. There is no dedicated packing service, packing page template, packing API route, or packing test suite in the application.
- Database packing tables already exist: packing_orders, packing_order_items, packing_material_consumption, packing_material_returns, packing_labour, packing_completions, packing_quality_checks, packing_wastage, packing_fg_transfers, and packing_order_status_history.
- Read-only counts: 2 packing orders, 4 order items, 2 labour rows, 2 FG transfer rows; material consumption, material returns, completions, QC, and wastage rows are currently 0.
- The two existing packing orders are DRAFT test-numbered records (TEST-COST-MATERIAL-001 and TEST-COST-002). Existing FG transfer rows are POSTED. These records were inspected only and were not changed.
- Existing item rows use 10 pieces per box. The user's packaging rule distinguishes 10-piece small boxes from 100-piece finished wall boxes (10 small boxes per finished box). The existing schema does not clearly model both packaging levels as separate entities, so this mapping must be resolved before operational integration.
- The packing order location references core.locations while FG transfer location references inventory.locations. Confirm the one-godown mapping before any stock posting.
- Existing nalki_orders schema includes both source_big_cone_order_id and source_baby_cone_order_id. Operational validation must enforce the user's rule that Nalki originates from Large Cone, never Baby Cone.
- No stock, packing order, labour, FG transfer, or master data was changed during this audit.

## Next safe implementation gate
Before activating packaging configuration in live packing, implement and test the dedicated packing service/UI against the existing tables, map 10-piece and 100-piece packaging levels explicitly, enforce the single physical godown, and pin the approved configuration version to each created packing document. Preserve the existing test rows and posted FG transfers.


## Location mapping follow-up — read-only clarification
- core.locations contains nine logical entries: Raw Material Store, Dyeing, Big Cone, Baby Cone, Nalki, Labeling, Packing, Finished Goods, and Dispatch.
- inventory.locations contains nine corresponding rows, each mapped through core_location_id; all nine currently have allow_stock=true.
- Existing packing order TEST-COST-002 has core location_id=7 (Packing). Its two POSTED FG transfer rows use inventory location id=5, which maps to core location id=8 (Finished Goods).
- These are logical process/stock-location records, not proof of nine physical godowns. The ERP must preserve the user's one physical godown rule: process stage must not be treated as separate warehouses. Before enabling stock postings, validate that all physical stock is held under the one approved godown and process_stage_id records the workflow stage. Do not change existing location rows or posted transfers as part of this audit.
