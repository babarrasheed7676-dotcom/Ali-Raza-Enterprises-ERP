# Baby Cone Source Handoff — Read-only Gap Audit
Date: 8 November 2026
Scope: Safe working copy; application source + PostgreSQL READ ONLY inspection.

## Executive result
Baby Cone has a read-only source preflight, measurement capture scaffolding, and database structures/guards. It does NOT yet have an operational Baby Cone DRAFT order creation, approval, or posting service/route. All seven Baby Cone tables currently contain zero rows.

## Critical source-handoff mismatch
- app/big_cone_draft_service.py defines the Big Cone output destination allow-list as DYEING.
- Big Cone output is constrained to 1.25 KG per jaali/dye cone and the Production Overview places BIG_CONE before DYEING. This matches the user's confirmed pre-dyeing winder process.
- app/baby_cone_draft_service.py source preflight instead selects POSTED production.big_cone_output_lines where destination_type='BABY_CONE', at RAW_STORE / BIG_CONE process stage.
- Therefore the current Baby Cone source query is not aligned with the Big Cone service's only permitted destination. It may return no source lines even after valid Big Cone postings.
- Do NOT simply add BABY_CONE to the pre-dyeing Big Cone destination allow-list: that would mix the dye-package preparation process with the downstream Baby Cone source process and could break the confirmed workflow.
- Resolve the real post-dyeing route and source document/stage before implementing Baby Cone DRAFT creation. The earlier historical route Dyeing -> Large Cone -> Baby Cone is not sufficient evidence that the pre-dyeing Big Cone order is the Baby Cone source.

## Current Baby Cone application surface
- app/baby_cone_draft_service.py has get_baby_cone_draft_source_preflight() only; its docstring states it is read-only and does not create orders, reserve stock, save costs, or post inventory.
- app/main.py exposes a protected Baby Cone source-preflight page and a separate Baby Cone measurement page/save endpoint.
- No Baby Cone order create/approve/post route was found.
- app/baby_cone_measurement_service.py reads measurement options from existing output lines with configuration snapshots; it is not an order-creation service.
- app/templates/baby_cone_source_preflight.html explicitly says draft creation remains disabled pending verified material/output, profile, labour/overhead, and loss rules.

## Database structure and safety
Seven tables inspected in schema production:
- baby_cone_orders
- baby_cone_material_lines
- baby_cone_output_lines
- baby_cone_cost_lines
- baby_cone_loss_lines
- baby_cone_measurements
- baby_cone_configuration_snapshots

All seven row counts were zero at audit time. Existing schema includes source_big_cone_output_line_id on material lines, source_material_line_id on output lines, a source Big Cone order header reference, measurement-to-output and measurement-to-approved-profile snapshot links, cost types (LABOUR, ELECTRICITY, MACHINE, MAINTENANCE, OTHER), and loss types (PROCESS_WASTAGE, BREAKAGE, HANDLING_LOSS, MACHINE_LOSS, LOST, OTHER).

Database triggers already protect important relationships:
- Baby Cone material source-output validation and source-material mutation locks.
- Baby Cone output source-material validation and output deletion guard.
- Measurement draft guard.
- Configuration snapshot guard.
- Baby Cone source-header mutation guard.

These are useful protections, but they do not constitute a complete transaction workflow. Trigger function bodies and full posting semantics must be reviewed before designing a writer.

## Implementation sequence (no business rule assumptions)
1. Identify the actual post-dyeing stock/document stage that feeds Baby Cone; keep the pre-dyeing Big Cone dye-package stage distinct.
2. Map exact source stock dimensions (variant, batch, one godown, process stage, OWN/PARTY owner, rate) and prevent double allocation across DRAFT/APPROVED orders.
3. Confirm Baby Cone variant/output definition and output-to-source material lineage.
4. Integrate only an approved effective MEASUREMENT_PROFILE snapshot; do not invent weight/yard values.
5. Capture salary-based labour and verified overhead; Baby Cone is not theka.
6. Define loss/reconciliation and variance rules from actual factory instructions.
7. Implement DRAFT-only service/route first, then separate approval and posting with permissions, CSRF, row locks, stock/ledger atomicity, audit events and rollback tests.
8. Do not enable production entry until departments/machines and required master data are genuinely configured.

## Safety boundary
Read-only audit only. No code, schema, master data, role, permission, production record, stock, ledger, or server process was changed. No test production record was created.
