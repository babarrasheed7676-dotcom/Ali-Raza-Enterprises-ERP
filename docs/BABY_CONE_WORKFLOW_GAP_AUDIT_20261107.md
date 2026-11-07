# Baby Cone Workflow Gap Audit — 7 November 2026

## Scope and safety
Read-only review of the active safe working copy, PostgreSQL catalog/data, and running FastAPI OpenAPI route list. No application code, database schema, records, stock, roles, permissions, or live processes were changed. Existing regression suites were not rerun.

## Runtime and repository synchronization
- Application health: `{"app":"ok","database":true}`.
- Public GitHub mirror baseline: `de8c2fb` (clean working tree at inspection).
- Five critical files previously compared against the safe working copy remain byte-for-byte aligned: `app/dyeing_draft_service.py`, `app/big_cone_draft_service.py`, `app/production_service.py`, `app/main.py`, and `app/templates/production.html`.

## Database findings
All seven Baby Cone operational tables inspected exist:
- `production.baby_cone_orders`
- `production.baby_cone_material_lines`
- `production.baby_cone_output_lines`
- `production.baby_cone_cost_lines`
- `production.baby_cone_loss_lines`
- `production.baby_cone_measurements`
- `production.baby_cone_configuration_snapshots`

At audit time all seven tables contained zero rows. Additional read-only integrity queries returned:
- Output lines / measured lines / unmeasured lines: 0 / 0 / 0.
- Cost lines: 0; loss lines: 0.
- Header-to-material/output quantity mismatches: 0.
- Measurements without a matching configuration snapshot: 0.
- Measurement snapshot variant mismatches: 0.

These are empty-dataset results, not proof that populated production workflows are correct.

## Existing application capability
- The only Baby Cone-specific path present in the running OpenAPI document is `/modules/production/baby-cone/measurements`.
- The measurement calculation module implements measured gross weight, empty-core tare, net yarn, measured yards, grams per yard, and optional target-yards-to-kg calculation.
- Measurement saving is constrained to a DRAFT parent order and a pinned approved `MEASUREMENT_PROFILE` snapshot matching the output variant.
- The measurement function does not post inventory, reserve stock, or calculate production cost.
- The schema already has separate Baby Cone cost and loss line tables, plus input/output line cost columns. No active Baby Cone order creation, approval, posting, cost-line entry, or loss-line entry endpoint was identified in the running route list.

## Safe next implementation sequence
1. Build the Baby Cone DRAFT order/material/output capture workflow, enforcing the one-godown model and source from Large Cone.
2. Pin approved measurement profile snapshots to eligible output variants and retain the existing measured weight-per-length evidence.
3. Capture actual Baby Cone salary/labour, machine and electricity costs using approved business inputs. Do not apply Nalki theka labour rules to Baby Cone.
4. Define and capture actual measured loss separately from unreconciled input/output difference; never derive measured wastage automatically from arithmetic balance.
5. Add read-only approval readiness covering source stock, exact ownership/party controls, measurements, costs, and reconciliation.
6. Only after business rules and independent approval are established, design posting, stock movement, cost allocation, audit and reversal controls.

## Explicit business-rule gates still required
- Confirm the factory's actual Baby Cone loss measurement and reconciliation method.
- Confirm how Baby Cone salary/labour, machine and electricity amounts are measured and allocated to output.
- Confirm which output measurement is mandatory for each real Baby Cone product variant and the approved tolerance.
- Confirm the exact operational source and ownership treatment for any PARTY-owned thread; do not assume the Nalki policy applies.

## Conclusion
Baby Cone has a reusable measurement calculation and measurement-save path, but the full order-to-cost-to-post workflow is not exposed by the current running API. The next safe milestone is DRAFT capture and evidence/readiness, not inventory posting. No dummy orders or master records should be created to fill the currently empty tables.
