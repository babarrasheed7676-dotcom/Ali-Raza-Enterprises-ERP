# Baby Cone Schema and Guard Review — 7 November 2026

## Scope
Read-only inspection of PostgreSQL table columns, constraints, indexes, and trigger/function definitions for Baby Cone and its Large Cone source. Also searched application and tests for Baby Cone cost/loss write paths. No code, database, records, permissions, or running process was changed.

## Verified database protections
- `inventory.stock_balances` has a unique exact-dimension key over company, item variant, batch, location, ownership type, owner party, and process stage; its quantity has a non-negative check.
- Baby Cone material rows require a positive KG quantity and have an exact `source_big_cone_output_line_id` FK to Large Cone output.
- `guard_baby_cone_source_output_line` requires a DRAFT Baby Cone order and a POSTED same-company Big Cone output whose destination is BABY_CONE. It validates item, batch, ownership, owner, unit, RAW_STORE, BIG_CONE stage, and parent source order. It locks the source output row and prevents total non-cancelled/non-reversed allocations from exceeding source output KG.
- Baby Cone output rows must point to their same-order material line and match item, batch, ownership, owner, unit, and godown; output stage must be BABY_CONE. Output quantity cannot exceed its source material quantity.
- Measurement rows are DRAFT-only, company/output-line scoped, and checked against their pinned profile snapshot, variant, approval flag, and required operator.
- Configuration snapshots are immutable and checked against the approved configuration version, company, key, payload, effective period, output variant, order creator, and order date.
- Header source Big Cone order cannot be changed after material lines exist.

## Remaining application/workflow gaps
- Application/test search found no Baby Cone cost-line or loss-line create/update service or route. The production overview only reads their counts.
- Database inspection found no DRAFT-only triggers on `baby_cone_cost_lines` or `baby_cone_loss_lines`. Their basic check constraints enforce non-negative cost and positive loss quantity, but do not enforce parent order status or costing/loss reconciliation.
- Cost line types currently allowed by the DB: LABOUR, ELECTRICITY, MACHINE, MAINTENANCE, OTHER. This is not yet a verified full overhead taxonomy for ARE; do not silently map every overhead to a guessed type.
- Loss types currently allowed: PROCESS_WASTAGE, BREAKAGE, HANDLING_LOSS, MACHINE_LOSS, LOST, OTHER. The schema does not define a measured-loss formula or approval tolerance.
- Header `wastage_quantity_kg` defaults to zero; it must not be populated from input-minus-output arithmetic and must not be described as measured wastage without an explicit recorded/reconciled loss line.

## Required contract before Baby Cone DRAFT workflow implementation
1. In one transaction, create the DRAFT header, source material rows, output rows, and approved measurement profile snapshots.
2. Lock the exact Large Cone output row during source allocation. Recompute remaining source KG and exact-dimension stock KG inside the write transaction; do not trust the read-only preflight result as a reservation.
3. Preserve company, variant, batch, location, OWN/PARTY owner, unit, process stage, and source output identity exactly. PARTY source requires a captured, immutable party rate.
4. Validate every output line against its same-order material line; do not infer conversion factors or output quantities.
5. Add explicit DRAFT-only application guards for cost/loss entry and edits. Decide the approved labour, electricity, machine and overhead capture method before cost roll-up.
6. Record measured loss by approved loss type, quantity, unit, reason, and evidence; reconcile material input against accepted output, byproduct and measured loss. Never auto-label arithmetic difference as wastage.
7. Approval/posting must remain separate from Save. No inventory movement or ledger entry until a separately reviewed posting implementation is authorized and tested.

## Current operational state retained
The live company currently has no POSTED Big Cone source orders, no approved Baby Cone measurement profiles, and no active departments or machines. The source preflight remains read-only and DRAFT creation remains disabled. No server restart was performed.
