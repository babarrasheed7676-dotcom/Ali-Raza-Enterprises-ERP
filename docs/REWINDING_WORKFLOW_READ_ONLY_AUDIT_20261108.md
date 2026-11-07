# Cone Rewinding Workflow — Read-Only ERP Audit — 8 November 2026

## Scope and safety

Read-only inspection of the safe working copy, application route/service references, and live PostgreSQL catalog/data. The database checks ran in a `REPEATABLE READ, READ ONLY` transaction. No application code, schema, records, permissions, stock, ledger, or server process was changed.

## Current ERP implementation findings

1. The database contains `production.rewinding_orders`, `production.rewinding_material_lines`, and `production.rewinding_output_lines`.
2. All three relations returned **0 rows** in the live read-only snapshot.
3. The order header has date/number/status, machine, department, operator, input/output quantity and units, input/output cone counts, wastage/variance, labour/electricity/machine/total cost, start/end times, remarks, and approval/posting audit columns.
4. Material and output lines carry item variant, batch, location, ownership type, owner party, process stage, quantity, unit, cone quantity and unit/total cost. Output lines additionally carry `output_type`.
5. The three tables have foreign keys to relevant company/user/machine/department/unit, batch/location/item variant, ownership/party/process-stage dimensions, and parent order. The schema therefore provides structural foundations, but empty rows do not prove an operational workflow exists.
6. Application source has no dedicated rewinding draft service, form/template, or create/approve/post route. `app/production_service.py` includes `rewinding_orders` only in the protected, read-only production dashboard count/status summary. `app/production_master_service.py` checks rewinding usage when protecting department/machine master changes.
7. The existing Big Cone workflow is a separate implementation (`big_cone_draft_service.py` and protected routes). Do not assume it implements the user's revised rewinding workflow.

## Known earlier reference — not treated as the new instruction

Earlier project context described purchased/received yarn → raw-material store → rewinding (four rewinders) → 1.25 kg dyeing cones → dyeing → dyed yarn → Big/Large Cone → Baby Cone or Nalki. This is historical context only. The user has now said the cone-rewinding flow has changed, but the exact revised sequence is not present in the currently available project files or the latest located master PDF. Do not implement or overwrite the old flow until the revised stages and material/output rules are supplied or the updated master PDF is made available.

## Required next review once revised flow is available

- Map each stage and handoff to existing process-stage/location dimensions while retaining the single physical godown.
- Confirm actual input item/count/fibre and source document/batch/ownership/party rules.
- Confirm output cone type, target weight/count, number of cones, acceptable variance, wastage/return/rework handling.
- Confirm whether rewinding precedes dyeing or is split into more than one rewinding operation, and which machine/rewinder is used at each step.
- Confirm labour/electricity/machine cost drivers and allocation basis; do not infer them from current header columns.
- Compare the new sequence with the existing Big Cone/Dyeing/Baby Cone/Nalki routes and stock lineage triggers before proposing implementation.
- Design DRAFT → separate approval → separate posting, with no stock/ledger mutation on ordinary Save.

## Current conclusion

**Rewinding is schema-present but application-workflow absent and data-empty** in the inspected live company snapshot. The ERP cannot yet be said to implement the user's revised cone-rewinding flow. The exact new flow must be incorporated into the master project record before implementation design is finalized.
