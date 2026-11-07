# ERP Stored-Routine Table Dependency Audit — 8 November 2026

## Scope and safety

Read-only catalog retrieval of pg_get_functiondef for all 46 routines in the eight application schemas, followed by static matching of schema-qualified relation references against pg_class. The transaction was explicitly set READ ONLY. No grants, role attributes, ownership, routines, triggers, DSN, app code, records, or server state were changed.

This is a dependency candidate map from routine source text, not a PostgreSQL parser or proof that each branch executes. It complements the Python direct-SQL and dynamic SQL audits.

## Results

- Stored routines inspected: 46 (33 trigger functions + 13 non-trigger routines).
- Dynamic EXECUTE / format() occurrences in the inspected routine definitions: 0.
- Schema-qualified references that resolved to actual relations in the eight application schemas: 52 distinct base tables.
- One additional schema-qualified match, inventory.post_stock_document, resolved to a routine rather than a relation; it is a nested routine call and not a table grant.
- No confirmed unqualified base-table reference was identified by the source review. The naive token pass returned variable names, record fields (NEW/OLD), aliases, and PL/pgSQL keywords; these are not grant targets.
- All 33 trigger functions remain SECURITY INVOKER, as previously catalog-verified. Their cross-table SELECT dependencies therefore matter to the runtime DML role and must be validated on a restored database.

## Table-level routine dependency matrix

Operations below are observed in routine source text. SELECT includes FROM/JOIN references. INSERT/UPDATE are separately listed where found. Absence of a write operation in this matrix is not proof that no other application route writes that table.

| Schema | Relation | Routine-source operations |
|---|---|---|
| accounting | journal_entries | SELECT |
| accounting | journal_lines | SELECT |
| configuration | config_versions | SELECT |
| core | document_sequences | UPDATE |
| core | locations | SELECT |
| core | users | SELECT |
| inventory | batches | SELECT |
| inventory | locations | SELECT |
| inventory | stock_balances | SELECT, INSERT, UPDATE |
| inventory | stock_document_lines | SELECT, INSERT, UPDATE |
| inventory | stock_documents | SELECT, INSERT, UPDATE |
| inventory | stock_ledger | INSERT |
| inventory | stock_reservation_lines | SELECT, INSERT, UPDATE |
| inventory | stock_reservations | SELECT, INSERT, UPDATE |
| inventory | transaction_types | SELECT |
| master | brands | SELECT |
| master | item_categories | SELECT |
| master | item_variants | SELECT |
| master | items | SELECT |
| master | ownership_types | SELECT |
| master | process_stages | SELECT |
| master | shades | SELECT |
| master | units | SELECT |
| production | baby_cone_configuration_snapshots | SELECT |
| production | baby_cone_material_lines | SELECT |
| production | baby_cone_orders | SELECT |
| production | baby_cone_output_lines | SELECT |
| production | big_cone_material_lines | SELECT |
| production | big_cone_orders | SELECT |
| production | big_cone_output_lines | SELECT |
| production | dyeing_consumption_lines | SELECT |
| production | dyeing_material_lines | SELECT |
| production | dyeing_orders | SELECT |
| production | dyeing_output_lines | SELECT |
| production | dyeing_unit_conversion_snapshots | SELECT |
| production | nalki_orders | SELECT |
| production | nalki_output_lines | SELECT |
| production | outside_labeling_orders | SELECT |
| production | outside_labeling_return_lines | SELECT |
| production | ownership_use_requests | SELECT |
| production | packing_fg_transfers | SELECT, UPDATE |
| production | packing_labour | SELECT |
| production | packing_material_consumption | SELECT |
| production | packing_order_items | SELECT, UPDATE |
| production | packing_orders | SELECT, UPDATE |
| production | packing_source_allocations | SELECT |
| purchasing | purchase_receipt_lines | SELECT |
| purchasing | purchase_receipts | SELECT |
| sales | dispatch_lines | SELECT |
| sales | dispatches | SELECT, UPDATE |
| sales | sales_order_lines | SELECT |
| sales | sales_orders | SELECT, UPDATE |

## High-impact write paths found inside routines

- inventory.post_stock_document: updates stock documents/balances, inserts stock ledger rows, and inserts/updates stock-document lines/balances. This is a high-impact stock-posting routine. Its exact route caller and restored-staging tests remain mandatory.
- inventory.approve_stock_document: updates stock documents; validates core.users, inventory.transaction_types and stock-document lines.
- core.get_next_document_no: updates core.document_sequences. The runtime must not receive blanket sequence rights on this evidence alone; validate function execution and sequence dependencies separately.
- sales.cancel_sales_order / confirm_sales_order / post_dispatch / reserve_sales_order_line: mutate sales and/or inventory reservation/dispatch data. Sales & Dispatch currently has no protected app route and is marked Planned; do not grant these routines to web runtime yet.
- production.post_packing_fg_transfer: updates production.packing_fg_transfers and calls stock approval/posting routines. No current app route/service caller was found; do not grant it to web runtime.
- production.calculate_packing_cost and calculate_packing_cost_test: read packing/source/stock-document data; they have no direct Python caller evidence in the current static scan.

## Trigger-only dependency implications

The 33 SECURITY INVOKER trigger functions read across production, configuration, master, inventory and core tables. Examples:
- Baby Cone / Big Cone lineage guards read upstream/downstream orders, material/output lines, process stages, locations and item variants.
- Dyeing guards read source orders/lines, item/category/variant/unit/ownership/stage/shade/brand masters, inventory batches/locations, and conversion snapshots.
- Packing guards read packing orders/items/allocations, Nalki and outside-labeling sources, process stages and configuration versions.
- Ownership guards read ownership requests, source lines/orders and configuration versions.
- Purchasing snapshot guards read receipt/receipt-line, item/unit masters and configuration versions.
- Accounting guards read journal headers and lines.
- Inventory stock-document trigger guards enforce immutability and ledger/journal consistency.

Do not assume these trigger reads are covered by grants on the directly modified table. On a restored staging copy, exercise each protected DML path under the candidate runtime role after PUBLIC EXECUTE revocation and verify all trigger guards still run. Do not grant runtime TRIGGER, schema CREATE, or routine ownership to work around a failure.

## Important interpretation limits

1. The source scan matches schema-qualified relation tokens and checks them against pg_class; it does not parse every SQL grammar form or resolve dynamic identifiers at runtime.
2. A table can be read by a routine without appearing in pg_depend for PL/pgSQL. Source inspection is necessary, but still needs review against the exact routine body and branch conditions.
3. SELECT in a trigger function does not imply the runtime should receive broad SELECT on the entire schema. Grant only the exact relations needed by reachable application DML and prove with staging tests.
4. This map does not include the complete direct Python CRUD matrix, route reachability, view/report usage outside the scanned code, or migration-only access.
5. Do not grant DELETE, TRUNCATE, DDL, TRIGGER, or blanket sequence privileges from this report.

## Next gates

- Merge this 52-table routine dependency set with the 70-table Python candidate matrix and the resolved dynamic Python table sets.
- Mark each object as reachable-runtime, trigger-only dependency, dormant/unreachable, or migration/admin-only.
- Resolve sequence behavior and exact function signatures on the restored staging copy.
- Test receipt/return approval and posting, accounting journal guards, production-stage guards, inventory stock-document guards, and ownership-use guard paths under a non-owner runtime candidate.
- Only then generate exact per-object grants and a rollback script for staging review.

## Status

Routine source extraction: complete, read-only.
Dynamic SQL in the 46 routine definitions: none found.
Routine-source relation dependency candidates: 52 base tables.
Final least-privilege runtime grants: not yet generated or applied.
Live database and runtime remain unchanged.

## Current row-count and route disposition of routine-only relations

A single consistent `REPEATABLE READ, READ ONLY` snapshot counted the ten routine-only relations. Exact row counts: `inventory.stock_ledger` 12; `inventory.stock_reservation_lines` 2; `inventory.stock_reservations` 2; `production.packing_fg_transfers` 2; `production.packing_labour` 2; `production.packing_material_consumption` 0; `sales.dispatch_lines` 3; `sales.dispatches` 3; `sales.sales_order_lines` 2; `sales.sales_orders` 2.

The stock ledger is reached by the protected purchasing stock-posting workflow through `inventory.post_stock_document`; preserve its routine-required INSERT/SELECT/UPDATE access only as validated in restored staging. Reservation and Sales relations have existing rows but no current protected Sales & Dispatch route; do not grant the runtime role access to them merely because stored routines reference them. Packing FG transfer/labour relations also contain existing records, including POSTED transfer rows, but `production.post_packing_fg_transfer` has no protected app route; preserve the records and keep runtime EXECUTE excluded. `production.packing_material_consumption` is currently empty.

Counts were used only to establish presence/absence; no row contents were read or changed.
