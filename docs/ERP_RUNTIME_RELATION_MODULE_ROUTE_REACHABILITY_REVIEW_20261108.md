# Runtime Relation Module and Route Reachability Review — 8 November 2026

## Purpose and safety boundary

This review advances the 93-relation consolidated candidate matrix by reconciling each relation's schema/module owner with the current module registry, imported service layer, and route evidence in app/main.py. It is a source-level reachability classification, not a final privilege grant list.

No application code, database object, role, ACL, DSN, data, or running process was changed. No server restart was performed.

## Module status observed in the current source

| Module / area | Registry status or direct evidence | Runtime classification |
|---|---|---|
| Inventory | Registry says “Database audit in progress”; dashboard and inventory data helpers are imported | Read paths exist; protected mutation route reachability must be assessed individually |
| Production | Registry says “Dyeing + measurement DRAFT only”; explicit production masters, Baby Cone measurement, Big Cone draft/readiness, and Dyeing draft/detail routes exist | Partial protected/draft workflow; do not infer approval/posting rights |
| Packing | Registry says “Draft-only workflow enabled”; packing, assortment, and random-source draft services are imported and routes exist | Draft-only; FG transfer routine remains dormant/unrouted |
| Sales & Dispatch | Registry says “Planned”; prior route scan found no sales/dispatch route decorators or service callers | Dormant; do not grant sales routine EXECUTE or sales-table runtime access on current evidence |
| Purchasing | Registry says “Read-only listings available”; protected receipt draft, approval, posting and return draft/approval/post routes are present | Active protected paths; strongest current basis for narrowly scoped runtime access |
| Accounting | Registry says “Planned”; direct /accounting/journal draft/approve/post routes and accounting report/fiscal-year service imports exist | Source contains reachable accounting routes despite stale/planned dashboard registry label; verify each route permission before grants |
| Reports | Registry says “Planned” | No blanket reporting access inferred from registry label |
| HR & Payroll | Registry says “Planned — implementation pending” | No runtime access inferred |
| Configuration | Registry says “Master data + draft approvals; integrations in progress”; explicit master and configuration draft/submit/approve/reject routes exist | Active but partial; configuration writes are permission-gated and CSRF-protected |

## Relation-level module classification for the consolidated 93 candidates

The schema prefix is a reliable module ownership signal, but not proof that every operation on every relation is reachable. Use the following interpretation for each row of ERP_CONSOLIDATED_RUNTIME_TABLE_ACCESS_CANDIDATE_MATRIX_20261108.md:

| Schema prefix | Relations in candidate matrix | Reachability conclusion |
|---|---:|---|
| accounting | 3 | Journal page reads accounts/journals/parties and accounting routes call draft/approve/post services. Treat journal entry and line writes as protected accounting operations; do not infer access to every accounting object from the three candidates alone. |
| configuration | 3 | Configuration version, audit and approval-event paths are used by configuration draft/approval workflow. Separate read, draft-write, approval-write operations. |
| core | 12 | Shared identity, authorization, company, fiscal-period, department and sequence dependencies. User/role/permission reads support auth; document sequence UPDATE is required only for the specific document-creation paths. Audit INSERT is source evidence, but actual audit coverage remains separately incomplete. |
| inventory | 9 | Inventory read helpers and stock-document workflows exist. Stock ledger/reservation tables are routine-only dependencies in the current source matrix; exact execution is gated by protected purchasing routes and trigger behavior. |
| master | 14 | Shared master data is consumed by configuration, purchasing, production and accounting pages/services. Several finite dynamic lookups are source-controlled; retain per-table and per-operation scoping. |
| production | 37 | Mixed status: reachable partial draft/readiness/measurement/master routes coexist with dormant or planned production tables. Do not grant all production relations merely because the schema is used. Routine-only packing FG transfer dependencies remain excluded. |
| purchasing | 12 | Receipt/return workflows are route-reachable and protected. Requisition, order, landed-cost, quality and supplier-price relations require individual route/service proof; do not treat every purchasing candidate as active write access. |
| sales | 4 | All four candidates are only present through dormant stored routines; Sales & Dispatch is Planned and no protected app route/service caller was found. Exclude from runtime grants. |

The three production routine-only relations are production.packing_fg_transfers, production.packing_labour, and production.packing_material_consumption. They are dependencies of the unrouted production.post_packing_fg_transfer routine. Exclude runtime access until a protected feature is implemented.

*Counts above are grouped by the 94-row candidate matrix's schema prefixes and routine-only dependency notes; they are not counts of proven reachable write grants.*

## Exact route evidence and constraints

- Purchasing receipt creation is a protected DRAFT save. Approval and posting are separate protected actions; posting requires both purchasing and inventory permissions.
- Purchasing returns have separate protected DRAFT, approval and posting routes; approval/posting require the corresponding purchasing and inventory permissions.
- Accounting journal routes separately gate create, approve and post. Journal creation is DRAFT-only; approval and posting are separate actions.
- Production master creation/update requires configuration.create; the master page requires production.view. This is a cross-module permission dependency, not permission to mutate all production tables.
- Configuration submit/draft routes require configuration.create; approve/reject require configuration.approve; request payload paths validate the CSRF cookie/header pair.
- Packing routes currently create DRAFT records. The database routine for packing FG transfer has no protected app route/service caller in the prior route/caller audit.
- Sales routines and tables remain unreachable from the current application route surface based on the prior route/caller scan and current registry status.

## Staging grant-design disposition

1. Potential active groups: only route-proven operations for Purchasing, Accounting journal, Configuration, and the explicitly implemented Production/Packing draft paths should proceed to per-function/per-table review.
2. Shared read dependencies: grant SELECT only where the exact protected route's service call needs it; do not infer global SELECT from schema membership.
3. Routine execution: keep the existing candidate allowlist limited to core.get_next_document_no, inventory.approve_stock_document, and inventory.post_stock_document, pending restored-staging validation. Do not grant Sales or packing-transfer routine EXECUTE.
4. Trigger functions: do not grant runtime EXECUTE merely because a trigger is attached. Validate trigger firing on a restored staging copy after PUBLIC EXECUTE revocation.
5. Sequences: derive USAGE/SELECT/UPDATE only from exact identity/serial/nextval behavior on protected paths. Do not grant ALL SEQUENCES.
6. Unknown/unqualified candidates: retain for review. A schema-level classification does not resolve unqualified SQL, nested trigger reads, external scripts, or planned feature dependencies.
7. No destructive cleanup: this review does not authorize dropping tables, revoking live privileges, changing ownership, or modifying the production runtime login.

## Remaining gates before any live privilege change

- Produce a function-level route-to-service-to-relation trace for each protected route, including SQL assembled by helper functions.
- Validate all trigger cross-table reads under a candidate non-superuser role on a restored staging database.
- Verify sequence privileges for each actual INSERT path.
- Confirm route-level permission checks and CSRF behavior for each write action.
- Review migration/external-script references for the 41 catalog tables without qualified source/routine references.
- Obtain separate explicit approval before any live role, password, ACL, ownership, DSN, or schema change.

## Status

Source-level module/route reconciliation added. It narrows the candidate set conceptually but intentionally does not manufacture per-table grants where route evidence is incomplete. Live ERP remains untouched.

## Follow-up — five dynamic SELECT dependencies confirmed

The expanded source scan traced five relations previously flagged for no qualified literal reference to protected application paths:

- `production.outside_dyeing_orders` and `production.rewinding_orders` are included in the fixed `PROCESS_ORDER_SOURCES` tuple in `app/production_service.py`. The production dashboard uses schema-qualified identifiers generated from this fixed tuple and runs inside a READ ONLY transaction. The module route is permission-gated through `MODULE_PERMISSIONS` before `get_production_dashboard_data()` is called.
- `production.dyeing_rework_orders`, `production.machine_capacities`, `production.machine_downtime`, and `production.rewinding_orders` are in the fixed machine reference tuple in `app/production_master_service.py`; `production.rewinding_orders` is also in the department reference tuple. These are SELECT EXISTS checks used by the protected machine/department update path `PUT /modules/production/api/masters/{kind}/{record_id}`, which requires `configuration.create` and uses the configuration action payload/CSRF path.

All five dependencies are SELECT-only in these call sites. Four were already present in the 93-relation matrix; `production.outside_dyeing_orders` was omitted and has now been added. The candidate matrix therefore contains 94 relations, including 37 production-schema relations. These five references do not justify any write grants on the referenced production history tables.

## Current data-state note for the five dynamic dependencies

A consistent `REPEATABLE READ, READ ONLY` count snapshot of all 41 source-gap relations returned zero rows for all 41. The five active dynamic dependencies are therefore currently empty, but their protected SELECT call sites still require read access if those routes are to operate under a restricted database role. No INSERT/UPDATE/DELETE grant follows from these read-only checks.

## Exact data state of ten routine-only relations

A consistent `REPEATABLE READ, READ ONLY` count snapshot was taken for the ten relations that are not directly referenced by current app source but are dependencies of stored routines. No row values were selected.

| Relation | Exact rows | Runtime disposition |
|---|---:|---|
| inventory.stock_ledger | 12 | Active inventory posting dependency through protected purchasing stock-posting path; keep only the exact routine-required operation in staging grant review |
| inventory.stock_reservation_lines | 2 | Existing records; Sales reservation workflow has no current protected app route; do not grant runtime access on current route evidence |
| inventory.stock_reservations | 2 | Existing records; Sales reservation workflow has no current protected app route; do not grant runtime access on current route evidence |
| production.packing_fg_transfers | 2 | Existing POSTED transfer records; posting routine has no protected app route; preserve records and exclude runtime routine EXECUTE |
| production.packing_labour | 2 | Existing records; only tied to dormant packing FG-transfer dependency in current routine/source map; preserve and exclude runtime access until route exists |
| production.packing_material_consumption | 0 | Dormant packing FG-transfer dependency; exclude runtime access until route exists |
| sales.dispatch_lines | 3 | Existing records; Sales & Dispatch is Planned with no protected route; preserve and exclude runtime access |
| sales.dispatches | 3 | Existing records; Sales & Dispatch is Planned with no protected route; preserve and exclude runtime access |
| sales.sales_order_lines | 2 | Existing records; Sales & Dispatch is Planned with no protected route; preserve and exclude runtime access |
| sales.sales_orders | 2 | Existing records; Sales & Dispatch is Planned with no protected route; preserve and exclude runtime access |

These results reinforce two separate rules: existing data must be preserved even when a module is dormant, and existing rows do not by themselves authorize the application runtime to access a table. The inventory stock ledger is distinct because the protected purchasing posting path invokes the inventory posting routine; its exact invoker permissions must be validated on restored staging.
