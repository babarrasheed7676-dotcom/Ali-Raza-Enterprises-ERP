# Consolidated Runtime Table-Access Candidate Matrix ? 8 November 2026

## Purpose and status

This is a merged source-evidence matrix, not an approved GRANT script. It combines the 7 November Python direct-SQL candidate matrix, the 8 November stored-routine relation matrix, and the manually resolved finite Python identifier maps. A table may appear because a dormant routine or read-only list references it; inclusion does not prove that the current web runtime should receive access. Route reachability, trigger invocation, sequence behavior, and restored-database validation remain separate gates.

- Unique candidate relations in this merged source set: **94**.
- Python literal operations are inherited from the prior AST matrix; dynamic operations are manually traced to finite source-controlled identifier maps and list query composition.
- Stored-routine operations are extracted from the 46 live routine definitions and filtered against actual catalog relations.
- No live ACL, role, owner, DSN, or data changes were made.

## Matrix

| Relation | Python literal ops | Python dynamic ops | Stored-routine ops | Classification note |
|---|---|---|---|---|
| accounting.accounts | FROM, JOIN | None | None | Python source candidate; validate route and exact operation |
| accounting.journal_entries | FROM, INSERT INTO, JOIN, UPDATE | None | SELECT | Python source candidate; validate route and exact operation |
| accounting.journal_lines | FROM, INSERT INTO, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| configuration.config_approval_events | FROM, INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| configuration.config_audit_events | FROM, INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| configuration.config_versions | FROM, INSERT INTO, JOIN, UPDATE | None | SELECT | Python source candidate; validate route and exact operation |
| core.accounting_periods | FROM, INSERT INTO, JOIN | None | None | Python source candidate; validate route and exact operation |
| core.audit_log | INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| core.company | FROM | None | None | Python source candidate; validate route and exact operation |
| core.departments | FROM, INSERT INTO, JOIN, UPDATE | None | None | Python source candidate; validate route and exact operation |
| core.document_sequences | UPDATE | None | UPDATE | Python source candidate; validate route and exact operation |
| core.fiscal_years | FROM, INSERT INTO, JOIN | None | None | Python source candidate; validate route and exact operation |
| core.locations | JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| core.permissions | JOIN | None | None | Python source candidate; validate route and exact operation |
| core.role_permissions | JOIN | None | None | Python source candidate; validate route and exact operation |
| core.roles | JOIN | None | None | Python source candidate; validate route and exact operation |
| core.user_roles | FROM | None | None | Python source candidate; validate route and exact operation |
| core.users | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| inventory.batches | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| inventory.locations | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| inventory.stock_balances | FROM, JOIN | None | INSERT, SELECT, UPDATE | Python source candidate; validate route and exact operation |
| inventory.stock_document_lines | FROM, INSERT INTO | None | INSERT, SELECT, UPDATE | Python source candidate; validate route and exact operation |
| inventory.stock_documents | FROM, INSERT INTO | None | INSERT, SELECT, UPDATE | Python source candidate; validate route and exact operation |
| inventory.stock_ledger | None | None | INSERT | routine-only source dependency; check route reachability |
| inventory.stock_reservation_lines | None | None | INSERT, SELECT, UPDATE | routine-only source dependency; check route reachability |
| inventory.stock_reservations | None | None | INSERT, SELECT, UPDATE | routine-only source dependency; check route reachability |
| inventory.transaction_types | FROM | None | SELECT | Python source candidate; validate route and exact operation |
| master.brands | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.fiber_types | FROM, INSERT INTO, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| master.item_categories | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.item_variants | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.items | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.machines | FROM, INSERT INTO, JOIN, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| master.ownership_types | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| master.parties | FROM, INSERT INTO, JOIN | SELECT | None | finite source-controlled identifier map/list |
| master.party_financial_profiles | INSERT INTO, JOIN | None | None | Python source candidate; validate route and exact operation |
| master.process_stages | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| master.shade_categories | FROM, INSERT INTO, JOIN, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| master.shades | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.units | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| master.yarn_counts | FROM, INSERT INTO, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| production.baby_cone_configuration_snapshots | FROM, INSERT INTO, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| production.baby_cone_cost_lines | FROM | None | None | Python source candidate; validate route and exact operation |
| production.baby_cone_loss_lines | FROM | None | None | Python source candidate; validate route and exact operation |
| production.baby_cone_material_lines | FROM | None | SELECT | Python source candidate; validate route and exact operation |
| production.baby_cone_measurements | FROM, INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| production.baby_cone_orders | FROM, JOIN | SELECT | SELECT | finite source-controlled identifier map/list |
| production.baby_cone_output_lines | FROM, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| production.big_cone_material_lines | FROM, INSERT INTO | None | SELECT | Python source candidate; validate route and exact operation |
| production.big_cone_orders | FROM, INSERT INTO, JOIN | SELECT | SELECT | finite source-controlled identifier map/list |
| production.big_cone_output_lines | FROM, INSERT INTO | None | SELECT | Python source candidate; validate route and exact operation |
| production.dyeing_consumption_lines | FROM, INSERT INTO, JOIN, UPDATE | SELECT, UPDATE | SELECT | finite source-controlled identifier map/list |
| production.dyeing_material_lines | FROM, INSERT INTO, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| production.dyeing_orders | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| production.dyeing_output_lines | FROM, INSERT INTO, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| production.dyeing_rework_orders | None | SELECT | None | finite source-controlled identifier map/list |
| production.dyeing_unit_conversion_snapshots | INSERT INTO, JOIN | None | SELECT | Python source candidate; validate route and exact operation |
| production.machine_capacities | None | SELECT | None | finite source-controlled identifier map/list |
| production.machine_downtime | None | SELECT | None | finite source-controlled identifier map/list |
| production.nalki_orders | None | None | SELECT | routine-only source dependency; check route reachability |
| production.nalki_output_lines | None | SELECT | SELECT | finite source-controlled identifier map/list |
| production.outside_dyeing_orders | None | SELECT | None | finite source-controlled PROCESS_ORDER_SOURCES tuple in app/production_service.py |
| production.outside_labeling_orders | None | SELECT | SELECT | finite source-controlled identifier map/list |
| production.outside_labeling_return_lines | None | SELECT | SELECT | finite source-controlled identifier map/list |
| production.ownership_use_requests | FROM, INSERT INTO, UPDATE | None | SELECT | Python source candidate; validate route and exact operation |
| production.packing_configuration_snapshots | FROM, INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| production.packing_fg_transfers | None | None | SELECT, UPDATE | routine-only source dependency; check route reachability |
| production.packing_labour | None | None | SELECT | routine-only source dependency; check route reachability |
| production.packing_material_consumption | None | None | SELECT | routine-only source dependency; check route reachability |
| production.packing_order_items | FROM, INSERT INTO | None | SELECT, UPDATE | Python source candidate; validate route and exact operation |
| production.packing_order_status_history | INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| production.packing_orders | FROM, INSERT INTO, JOIN | SELECT | SELECT, UPDATE | finite source-controlled identifier map/list |
| production.packing_source_allocations | FROM, INSERT INTO, UPDATE | INSERT, SELECT, UPDATE | SELECT | finite source-controlled identifier map/list |
| production.production_executions | FROM | SELECT | None | finite source-controlled identifier map/list |
| production.production_orders | JOIN | SELECT | None | finite source-controlled identifier map/list |
| production.production_targets | FROM | SELECT | None | finite source-controlled identifier map/list |
| production.recipes | FROM | None | None | Python source candidate; validate route and exact operation |
| production.rewinding_orders | None | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_configuration_snapshots | INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| purchasing.purchase_landed_costs | None | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_order_lines | FROM, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_orders | FROM, JOIN | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_receipt_lines | FROM, INSERT INTO, JOIN | SELECT | SELECT | finite source-controlled identifier map/list |
| purchasing.purchase_receipts | FROM, INSERT INTO, JOIN, UPDATE | SELECT | SELECT | finite source-controlled identifier map/list |
| purchasing.purchase_requisition_lines | None | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_requisitions | None | SELECT | None | finite source-controlled identifier map/list |
| purchasing.purchase_return_lines | FROM, INSERT INTO | None | None | Python source candidate; validate route and exact operation |
| purchasing.purchase_returns | FROM, INSERT INTO, JOIN, UPDATE | SELECT | None | finite source-controlled identifier map/list |
| purchasing.receipt_quality_inspections | None | SELECT | None | finite source-controlled identifier map/list |
| purchasing.supplier_item_prices | None | SELECT | None | finite source-controlled identifier map/list |
| sales.dispatch_lines | None | None | SELECT | routine-only source dependency; check route reachability |
| sales.dispatches | None | None | SELECT, UPDATE | routine-only source dependency; check route reachability |
| sales.sales_order_lines | None | None | SELECT | routine-only source dependency; check route reachability |
| sales.sales_orders | None | None | SELECT, UPDATE | routine-only source dependency; check route reachability |

## Access-design rules

1. Keep SELECT, INSERT, UPDATE, DELETE, and sequence privileges separate; a source reference is not a blanket CRUD grant.
2. Treat SECURITY INVOKER trigger dependencies as required reads for the exact DML paths that fire them; prove this after PUBLIC EXECUTE revocation on restored staging.
3. Do not grant runtime EXECUTE to dormant Sales & Dispatch or packing FG-transfer routines while no protected route exists.
4. Do not grant blanket DELETE, TRUNCATE, TRIGGER, schema CREATE, DDL, or ALL SEQUENCES.
5. Route reachability is not fully encoded per row in this matrix. Purchase receipt/return approval and posting paths are protected and currently call the three reviewed inventory/document routines; other modules require separate route verification.
6. This matrix does not replace review of migrations, external scripts, dynamic SQL outside the scanned call forms, or PostgreSQL routine semantics.

## Status

Consolidated candidate matrix generated from read-only source/catalog evidence. Not a runtime grant list. No live database changes performed.
