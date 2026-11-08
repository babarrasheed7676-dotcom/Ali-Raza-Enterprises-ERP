# Cone Rewinding — Source Integration Gap Note — 8 November 2026

## Purpose and safety
Follow-up read-only source review after the rewinding schema/workflow audit. This note records integration conflicts that must be resolved against the user's revised factory flow before implementation. No application code, database schema, rows, roles, permissions, stock, ledger, or server process was changed.

## Confirmed source findings
1. `app/production_service.py` includes `rewinding_orders` in the production dashboard's fixed process-order source list. This is a SELECT/count/status summary only; it is not a transaction workflow.
2. The same file's process-stage display ordering is hard-coded as:
   `PURCHASE → BIG_CONE → DYEING → BABY_CONE → NALKI → LABELING → PACKING → FINISHED_GOODS`.
   There is no `REWINDING` entry in that display-order map.
3. The 6-Nov Production Phase 1 overview records 8 active process stages and explicitly says the production workflow tables, including Rewinding, were empty at that checkpoint. It also recorded zero active machines and zero active departments at that checkpoint.
4. `app/production_master_service.py` treats `production.rewinding_orders` as a machine/department history reference when protecting production masters. This is a reference-integrity safeguard, not evidence of a usable Rewinding form or route.
5. The 8-Nov foreign-key dependency audit confirms the Rewinding header/material/output tables are structurally connected to machine, department, user, unit, batch, location, item variant, ownership and process-stage masters.
6. Earlier live read-only audit found zero rows in all three Rewinding relations and no dedicated Rewinding create/draft/approve/post application workflow.

## Integration risks to resolve against the revised flow
- The dashboard's current hard-coded process ordering may become misleading if Rewinding is moved, split, repeated, or made conditional in the revised sequence.
- The configured process-stage master currently does not evidence a dedicated Rewinding stage in the 8-stage checkpoint. Do not insert one until the revised process definition and stage semantics are confirmed.
- The schema can represent machine/department, input/output, ownership and process-stage references, but the exact revised input/output handoffs, cone specifications, wastage/rework, costing, and next-stage destination are not yet established.
- Machine/department setup was empty in the 6-Nov checkpoint. Any implementation plan must include verified machine/department setup readiness, without inventing dummy masters.

## Safe implementation order after revised-flow source is received
1. Extract the exact revised sequence from the changed master PDF or user-provided written process.
2. Build a stage-by-stage crosswalk against existing process stages, one physical godown, source documents/batches, OWN/PARTY ownership, and downstream production modules.
3. Reconcile the Production Dashboard's display order and stage labels to the approved sequence.
4. Specify Rewinding draft-entry fields, validation, machine/operator selection, material/output lineage, wastage/rework and costing from confirmed rules.
5. Implement protected DRAFT save, separate approval and separate posting only after explicit authorization; test on the safe working copy with no live stock/ledger mutation until posting is explicitly tested and approved.

## Explicit non-decisions
- This note does not declare that Rewinding must occur before or after Dyeing.
- It does not revive the historical 4-rewinder/1.25 kg-cone sequence as the current rule.
- It does not authorize schema changes, stage-master inserts, machine/department inserts, permission grants, stock movement, or production posting.
- The changed master PDF has not yet been located in the working-copy evidence reviewed for this note.

## Status
Source integration gap review complete. Awaiting the revised-flow source for a correct crosswalk and implementation specification.
