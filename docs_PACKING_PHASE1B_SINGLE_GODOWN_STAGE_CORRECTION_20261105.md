# Ali Raza Enterprises ERP — Packing Phase 1B
Date: 05-Nov-2026
Working copy: ARE ERP SAFE WORKING COPY CSS FIXED 18-Oct-2026

## Purpose
Correct the Packing draft workflow so it treats Nalki and Labeling as process stages, not warehouses, and prevents already-finished goods from being selected for another packing run.

## Read-only database findings
- Legacy core.locations / inventory.locations contain 9 paired location records: RAW_STORE, DYEING, BIG_CONE, BABY_CONE, NALKI, LABELING, PACKING, FG_STORE and DISPATCH. This legacy layout is not the target physical warehouse model; the business rule remains one physical godown with process_stage_id tracking.
- Current NALKI-CHANNEL-1 stock: 300 pieces at FINISHED_GOODS only; excluded from new packing.
- Current NALKI-GOLDEN_CHAIN-1 stock: 18 pieces at NALKI + 5 pieces at LABELING = 23 eligible pieces; 100 pieces at FINISHED_GOODS excluded. 23 is insufficient for one 100-piece finished wall box.
- Therefore the corrected packing form currently returns zero selectable variants. This is intentional and prevents repacking FG stock or creating a partial finished wall box.
- Nalki production orders: 0; Nalki output lines: 0; outside-labeling orders: 0; outside-labeling Nalki lines: 0; outside-labeling return lines: 0. Source-order traceability cannot be exercised against real upstream documents yet.
- Packaging master currently has one generic PACK_BOX-STD variant and one PACK_BAG-STD variant; neither has stock. The generic PACK_BOX variant does not distinguish the 10-piece small box from the 100-piece finished wall box. Do not assume either meaning until confirmed.
- NALKI_TUBE-STD has 100 OWN pieces at the NALKI process stage.
- Existing packing orders 9 and 10 remain DRAFT; packing order 10 has two POSTED FG transfers. Existing records are preserved.

## Code changes
- Replaced the old PACKING core-location dependency with eligible source process-stage codes NALKI and LABELING.
- Packing form stock query now reads master.process_stages and excludes FINISHED_GOODS.
- Form lists only active Nalki variants with at least 100 OWN pieces available.
- Server validates the requested total pieces against the currently available OWN source-stage balance.
- New draft header leaves location_id NULL; a draft does not choose a physical warehouse. No separate Packing warehouse is created or selected.
- No stock reservation, stock consumption, FG transfer, cost posting, labour posting, or accounting entry was introduced.

## Tests and verification
- Python compilation passed.
- Packing + configuration test suites: 42/42 passed.
- Jinja packing form rendered successfully with the new empty-state message.
- Live health endpoint returned app=ok and database=true.
- Corrected live form data returned variants=[] because eligible OWN stock is below 100 pieces.
- Counts remain unchanged: 2 packing orders, 4 packing order items, 2 packing labour rows, 2 packing FG transfers, 0 audit_log rows.
- No database schema, business data, stock, location rows, permissions or existing POSTED transfers were changed.

## Backup
- BACKUP_PACKING_STAGE_LOCATION_FIX_20261105 contains copies of app/packing_service.py, app/main.py, app/templates/packing.html and tests/test_packing_service.py before Phase 1B changes.

## Remaining implementation gates
1. Confirm whether PACK_BOX-STD represents the 10-piece small box, the 100-piece finished wall box, or whether two distinct variants are required.
2. Implement source-order/return-line traceability when Nalki and outside-labeling records exist; current packing header has order-level source references but no per-item source-line reference.
3. Add small-box empty returns, material issue/return, Nalki-only theka labour, QC, wastage, and controlled FG posting only after the packaging-item meaning and source mapping are settled.
4. Keep one physical godown and use process_stage_id for workflow stages. Do not migrate legacy location balances or alter existing posted transfers without an explicit, backed-up migration plan.


## Phase 2A — Draft-stage domain validation groundwork
Date: 05-Nov-2026
Backup: BACKUP_PACKING_PHASE2_RULES_20261105

### Verified existing structures and controls
- Existing dedicated tables already exist for packing completions, FG transfers, labour, material consumption, material returns, QC and wastage. This phase did not create or modify schema.
- Existing material-consumption triggers enforce that a linked stock document line is a Production Consumption transaction, matches the selected item variant, and that total active issue quantities do not exceed the inventory line's issued quantity. A table check also enforces used + returned + wasted <= issued.
- Packing material returns have condition values GOOD, DAMAGED, PARTIAL, OTHER and statuses PENDING, RECEIVED, POSTED, CANCELLED. The return table links to a generic material variant and an inventory location; it is not yet safe to use for empty small boxes until the small-box packaging SKU is confirmed.
- QC statuses allowed by schema are PENDING, PASSED, PARTIAL, FAILED, REINSPECTION and CANCELLED. The DB check requires passed + rejected <= inspected.
- Wastage types allowed by schema: NALKI, TUBE, PACKING_BOX, LABEL, PLASTIC_BAG, CARTON, OTHER.
- Labour statuses allowed: PENDING, APPROVED, POSTED, CANCELLED. Existing two packing labour rows are APPROVED; no new labour rows were created.
- Nalki order statuses include DRAFT, APPROVED, POSTED, CANCELLED, REVERSED. Outside-labeling includes DRAFT, APPROVED, SENT, PARTIAL_RETURN, RETURNED, CANCELLED, REVERSED.

### Code groundwork added (pure validators only)
- Material quantities: nonnegative and used + returned + wasted cannot exceed issued.
- Empty small-box returns: good + damaged returns cannot exceed issued small boxes; no packaging SKU assumption is made.
- QC: inspected quantity must be positive; passed/rejected are nonnegative; passed + rejected cannot exceed inspected; status derives as PASSED, PARTIAL or FAILED.
- Wastage: schema-approved type, positive quantity and mandatory reason (maximum 500 characters).
- Packing labour: positive box quantity, nonnegative rate, amount calculated as boxes × rate; labour type fixed to PACKING. This does not create Baby Cone salary or theka entries.
- These functions are not yet connected to UI routes or persistence. They are validation groundwork only; no business rows are created.

### Tests
- Python compilation passed.
- Packing + configuration test suites: 47/47 passed.
- No schema, DB rows, stock, accounting, roles, permissions, existing approvals or posted transfers were changed.

### Remaining gate
Confirm whether PACK_BOX-STD means the 10-piece small box, the 100-piece finished wall box, or whether separate SKUs are required. Empty box return/material issue UI must wait for this to avoid misclassifying stock.
