# Baby Cone Cost and Loss Implementation Contract — 7 November 2026

## Purpose and safety boundary

This document records the verified live PostgreSQL shape and the minimum safe application contract for a future Baby Cone DRAFT cost/loss entry milestone. This is documentation only. No database objects, application code, production records, permissions, stock, or running processes were changed.

## Live schema facts verified read-only

### `production.baby_cone_cost_lines`

- Parent link: required `baby_cone_order_id`, FK to `production.baby_cone_orders(id)`, ON DELETE CASCADE.
- Line identity: required `line_no`; unique per parent with `uq_baby_cone_cost_line`.
- Cost classification: required `cost_type`; DB allow-list is `LABOUR`, `ELECTRICITY`, `MACHINE`, `MAINTENANCE`, `OTHER`.
- Description and notes are optional.
- Quantity, unit, and unit rate are nullable. Quantity and unit rate, when present, must be non-negative.
- Amount is required and non-negative.
- Amount precision is numeric(20,6); quantity and unit rate are numeric(18,6).
- No company_id exists on the line; company scoping must be enforced by joining and locking the parent order.
- No DRAFT-only trigger exists on this table.
- No DB check currently enforces amount = quantity × rate, nor does it define whether amount is entered directly or calculated.

### `production.baby_cone_loss_lines`

- Parent link: required `baby_cone_order_id`, FK to `production.baby_cone_orders(id)`, ON DELETE CASCADE.
- Line identity: required `line_no`; unique per parent with `uq_baby_cone_loss_line`.
- Loss classification: required `loss_type`; DB allow-list is `PROCESS_WASTAGE`, `BREAKAGE`, `HANDLING_LOSS`, `MACHINE_LOSS`, `LOST`, `OTHER`.
- Quantity is required, strictly positive, numeric(18,3); unit is required.
- Item variant and batch are optional.
- Unit cost and total cost are optional and non-negative when supplied.
- Reason and notes are optional.
- No company_id exists on the line; company scoping must be enforced through the parent.
- No DRAFT-only trigger exists on this table.
- No source material-line/output-line FK, ownership type, owner party, location, or process-stage dimension exists. Therefore a loss row cannot currently prove which exact source stock dimension it consumes or reconcile loss to a particular material line.
- There is no evidence/attachment column in this table.

### `production.baby_cone_orders`

- Status allow-list: DRAFT, APPROVED, POSTED, CANCELLED, REVERSED.
- Header cost totals exist for labour, electricity, machine, and total process cost; all are non-negative and default to zero.
- `wastage_quantity_kg` is required, non-negative, and defaults to zero.
- Header variance is nullable and non-negative.
- A trigger protects source Big Cone order changes after material rows exist.
- The only non-internal trigger found on the header/cost/loss tables in this inspection was the source-header-change guard. No cost/loss child-row DRAFT guard was present.

## Safe application contract for future DRAFT entry

1. Every create, update, and delete request must resolve the parent using both document ID and the authenticated user's company ID. Never trust a submitted company ID or parent ID without scoped lookup.
2. Start a transaction and lock the parent header row with `SELECT ... FOR UPDATE`. Re-check that its status is exactly `DRAFT` while holding the lock. Reject all child mutations for APPROVED, POSTED, CANCELLED, or REVERSED documents.
3. Keep all cost/loss changes in the same transaction as their audit-log entries. Use parameterized SQL and decimal arithmetic; reject NaN, infinity, negative amounts, invalid units, invalid classifications, and out-of-range precision before writing.
4. Allocate line numbers under the parent-row lock; do not calculate MAX(line_no)+1 outside the transaction.
5. Cost line amount semantics must be decided before implementation. If amount is calculated, require quantity and unit rate together and calculate with Decimal using the approved currency/rounding policy. If direct amount entry is permitted, label it as manually entered and do not claim it equals quantity × rate. Do not silently mix both modes.
6. Header cost roll-up must be updated atomically from the saved child rows only after ARE approves the cost capture taxonomy and the exact mapping of each cost type to header totals. Do not infer that MAINTENANCE or OTHER belongs to labour, electricity, or machine.
7. PARTY thread electricity/cost allocation must not be confused with Nalki theka. Baby Cone labour remains salary/labour and overhead, not Nalki piece-rate/theka.
8. Loss rows must not update `wastage_quantity_kg`, inventory, or ledger until loss-line lineage and measurement rules are resolved. The current loss schema cannot identify the exact source material line or OWN/PARTY stock owner/location dimensions.
9. Never set measured wastage from input minus output. Keep input/output arithmetic labelled as an unreconciled difference until accepted output, byproduct, and independently recorded loss are reconciled under approved rules.
10. Save remains DRAFT only. Approval and inventory posting are separate future milestones requiring their own permission, CSRF, approval checks, audit trail, idempotency, stock-ledger design, and explicit implementation review.

## Focused test matrix required before enabling any write route

| Area | Required test |
|---|---|
| Parent scope | Existing order in another company is indistinguishable from not found; no child row is written. |
| Parent status | DRAFT accepts valid child changes; APPROVED, POSTED, CANCELLED, REVERSED reject create/update/delete. |
| Concurrency | Two simultaneous line creations cannot duplicate line_no or bypass status re-check. |
| Cost classification | Each allowed type accepted; unknown and case/whitespace variants rejected or normalized by an explicit documented policy. |
| Cost numeric | Negative, NaN, infinity, excess precision, incomplete quantity/rate pair rejected. |
| Cost semantics | Manual amount and calculated amount paths are distinct and tested against the approved rounding rule. |
| Roll-up | Header totals exactly match eligible child costs under the approved mapping; delete/update recomputes atomically. |
| Loss numeric | Zero, negative, NaN, infinity, wrong unit, excess precision rejected. |
| Loss lineage | Until schema/business rules provide source-line and exact stock-dimension lineage, loss cannot be treated as posted stock loss or measured wastage. |
| Audit | Create/update/delete logs identify actor, company, parent, line, old/new values, and reason; rollback leaves neither data nor audit row. |
| No side effects | DRAFT save changes no stock balance, stock ledger, GL, or source Big Cone allocation. |

## Unresolved ARE decisions — do not guess

- Which actual Baby Cone labour inputs are salary-based and how salary is allocated to a production order/shift.
- Whether electricity is captured from a meter, machine-hour rate, bill allocation, or another approved source.
- Whether machine depreciation, maintenance, consumables, and other overhead are included, and their approved allocation basis.
- Whether cost rows are direct amount, quantity × rate, or both with explicit modes.
- Which physical loss categories are measurable in Baby Cone, what unit and evidence are required, and who verifies them.
- Whether loss must be tied to a material line, batch, ownership owner, or godown dimension; current table cannot store all of these.
- Whether loss is a process expense, a stock adjustment, or a non-stock operational record; no posting semantics should be assumed.

## Result

The database currently supports basic child-row storage and numeric checks, but not safe lifecycle enforcement or full material-loss traceability. The next implementation must not add cost/loss write routes until the unresolved ARE rules are confirmed and the DRAFT-only protection is enforced transactionally (preferably in both application logic and DB triggers). No live server restart is part of this documentation milestone.

## Existing application authorization and CSRF patterns checked

A read-only application-code review confirmed:

- `production.create`, `production.approve`, and `production.post` already exist in the permission catalog. The proposed role matrix assigns DRAFT creation to PRODUCTION_OPERATOR and approval/posting to PRODUCTION_HEAD. This is a design catalog, not proof that any live user has those permissions.
- The existing Baby Cone measurement page and save route both require `production.create`. Its form POST validates `are_erp_csrf` cookie against the submitted `csrf_token` using constant-time comparison before calling the service.
- The source preflight GET is protected by `production.view` and sends `Cache-Control: no-store`.
- `write_audit_log` writes through the caller's transaction, so audit and child-row mutations can commit or roll back together.
- No Baby Cone cost-line or loss-line routes were found. Existing measurement route does not implement cost/loss CRUD and must not be treated as a substitute.

### Route-level blueprint (not implemented)

- Keep cost/loss create, update, and delete under `production.create`; require the same CSRF validation used by the existing measurement form.
- Resolve the user from the signed-in session. Accept only order ID and line payload; never accept company ID, user ID, status, audit actor, or stock dimensions as trusted authority from the browser.
- In the service transaction, select the parent by `id + company_id FOR UPDATE`, then require status DRAFT before every child-row mutation.
- Log each child mutation using `write_audit_log` with the exact table name, row ID, parent document number, old/new values, and a factual reason. Keep audit writes in the same transaction.
- Do not expose approval or posting endpoints as part of the DRAFT cost/loss work. Existing permission codes do not authorize implementation or live permission changes by themselves.
- Before enabling the UI, verify all role grants in the live database and add focused tests for cross-company access, CSRF failure, status races, child CRUD, audit rollback, and no stock/ledger side effects.


## Comparison with existing production cost capture

A read-only review of existing services shows why their current costing code cannot be copied into Baby Cone unchanged:

- Big Cone captures three header amounts only: labour, electricity, and machine. Its `_money` validator rejects non-finite/negative values, enforces a maximum of six decimal places, and the header total is the sum of those three values. It has no detailed cost-line capture or verified output allocation basis; its readiness preflight therefore blocks approval while cost allocation remains unresolved.
- Dyeing captures six header amounts: labour, machine, electricity, water, boiler fuel, and drying. `normalize_dyeing_process_costs` validates each as non-negative PKR numeric(20,6) and sums the six fields. This is a process-specific fixed-header model, not evidence that Baby Cone uses the same components or allocation policy.
- Baby Cone differs from both: it has a child cost-line table with five allowed types, optional quantity/rate, required amount, and a header with only labour/electricity/machine totals. There is no verified mapping for MAINTENANCE or OTHER, and no confirmed method to roll up child rows to the header.

Implementation conclusion: reuse only the general decimal-validation and transaction/audit patterns after review. Do not reuse Dyeing's six-field taxonomy, Big Cone's three-field taxonomy, or either module's header sum as Baby Cone's business rule without explicit ARE costing approval.
