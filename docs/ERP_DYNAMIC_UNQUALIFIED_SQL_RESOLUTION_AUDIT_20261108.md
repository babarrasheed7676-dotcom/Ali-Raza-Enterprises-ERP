# ERP Dynamic and Unqualified SQL Resolution Audit — 8 November 2026

## Scope and safety

Read-only static AST inspection of all 41 Python files under app/ in the Git mirror, followed by targeted source review of every dynamic execute argument and SQL-fragment composition site found by the scan. No application code, database object, role, grant, DSN, production record, or server state was changed.

This audit extends (does not replace) the 7 November direct SQL candidate matrix. It is source-level evidence, not proof of runtime reachability or final grant approval.

## Scanner results

- Python files scanned: 41.
- SQL clause-reference hits from the expanded FROM/JOIN/INSERT/UPDATE/DELETE/TRUNCATE scan: 638.
- Dynamic execute/executemany first arguments requiring manual review: 12.
- Six apparent unqualified names from the regex pass were SQL aliases, keywords, or CTE identifiers (including OF, SET, WHERE, l, descendants, own_stage_stock), not confirmed unqualified base tables.
- The earlier schema-qualified-only scan recorded 598 qualified table-reference hits and 70 distinct table candidates. The 638 figure uses a broader clause matcher and must not be substituted for the earlier qualified-only metric.

No confirmed unqualified base-table access was identified in the 12 dynamic sites reviewed. Dynamic fragments were traced to finite in-source maps, tuples, or fixed dictionaries listed below. This does not cover SQL constructed outside Python, external scripts, runtime database clients, or arbitrary indirect SQL in every stored routine.

## Dynamic SQL sites resolved

| Source | Dynamic fragment | Resolved object set | Operations in the reviewed site | Source control |
|---|---|---|---|---|
| app/configuration_master_service.py | master.{table} row lock | master.brands, master.units, master.shades, master.item_variants, master.yarn_counts, master.fiber_types, master.shade_categories, master.item_categories, master.items | SELECT | record_type must be in _ALLOWED_TYPES; table chosen from fixed literal map |
| app/ownership_use_service.py | source line table / quantity column / parent order / FK | production.dyeing_consumption_lines + production.dyeing_orders; production.packing_source_allocations + production.packing_orders | SELECT FOR UPDATE; UPDATE source line; later fixed UPDATE snapshot paths | module restricted to DYEING or PACKING; fixed MODULE_TABLES and conditional literals |
| app/ownership_use_service.py | second source line read | production.dyeing_consumption_lines + production.dyeing_orders; production.packing_source_allocations + production.packing_orders | SELECT FOR UPDATE | use_module selects only the two reviewed branches; request row is database-derived |
| app/packing_random_draft_service.py | source table lock | production.nalki_output_lines; production.outside_labeling_return_lines | SELECT FOR UPDATE | SOURCE_TABLE_BY_TYPE uses the two fixed random source constants |
| app/packing_random_draft_service.py | source-id column | production.packing_source_allocations.nalki_output_line_id OR .outside_labeling_return_line_id | INSERT | source type chooses one of two literal column names; target table remains fixed |
| app/production_master_service.py | department usage scan | production.baby_cone_orders, big_cone_orders, dyeing_orders, nalki_orders, outside_labeling_orders, packing_orders, production_orders, production_targets, rewinding_orders; plus master.machines | SELECT EXISTS | finite local tuple of literal table names |
| app/production_master_service.py | machine usage scan | production.baby_cone_orders, big_cone_orders, dyeing_orders, dyeing_rework_orders, machine_capacities, machine_downtime, nalki_orders, production_executions, production_orders, production_targets, rewinding_orders | SELECT EXISTS | finite local tuple of literal table names |
| app/purchasing_service.py | SELECT COUNT(*) + spec["from_where"] | See purchasing section table map below | SELECT | section key resolves into fixed PURCHASING_SECTIONS dictionary |
| app/accounting/report_service.py | purchase status loop | purchasing.purchase_receipts; purchasing.purchase_returns | SELECT | two fixed tuple values |
| app/db.py | count/page wrapper around supplied SQL | Wraps the fixed local configuration query strings in get_configuration_master_data | SELECT | caller query dictionary is local fixed code, not user-provided SQL |
| app/production_master_service.py | SQL concatenation of reference EXISTS clauses | same finite department/machine reference sets above | SELECT | concatenates only generated fixed fragments and parameter placeholders |
| app/production_master_service.py | SQL concatenation for master machine reference check | master.machines plus finite production machine-reference set | SELECT | generated from the finite local machine_refs tuple |

## Purchasing section SELECT map

The source-level AST literal extraction resolved all fixed section definitions used by the generic purchasing list query:

| Section | Referenced tables |
|---|---|
| suppliers | master.parties |
| requisitions | purchasing.purchase_requisitions, purchasing.purchase_requisition_lines |
| orders | purchasing.purchase_orders, purchasing.purchase_order_lines, master.parties |
| receipts | purchasing.purchase_receipts, purchasing.purchase_receipt_lines, purchasing.purchase_orders, master.parties |
| returns | purchasing.purchase_returns, purchasing.purchase_receipts, master.parties |
| landed-costs | purchasing.purchase_landed_costs, purchasing.purchase_receipts, master.parties |
| quality | purchasing.receipt_quality_inspections, purchasing.purchase_receipts, master.parties |
| prices | purchasing.supplier_item_prices, master.item_variants, master.items, master.parties, master.units |

These are read paths in the generic section listing query. They do not by themselves establish that each corresponding module has a fully implemented create/approve/post workflow. Route availability and write paths must be separately checked before any write grant is included.

## Operation-level implications

1. Configuration master dynamic identifier: SELECT is needed for the selected master record lock; the corresponding create/update branches use fixed table-specific SQL. The map does not justify grants on arbitrary master tables outside the nine listed names.
2. Ownership-use requests: DYEING reads/updates dyeing_consumption_lines and reads dyeing_orders; PACKING reads/updates packing_source_allocations and reads packing_orders. Both paths also access production.ownership_use_requests and cross-schema policy/master/user tables via fixed SQL. Include these indirect dependencies in the trigger/service matrix.
3. Random packing: source-line locks are SELECT FOR UPDATE on two fixed source tables. DRAFT creation inserts production.packing_order_items, production.packing_source_allocations and production.packing_order_status_history. No posting/stock movement is performed by this draft service. Its source-table SELECT locks and inserts must not be confused with stock ledger posting.
4. Production master maintenance: department/machine deactivation checks issue SELECT EXISTS against the finite reference lists. They do not dynamically update or delete those history tables. Existing machine/department create/update statements remain fixed SQL.
5. Purchasing list sections: dynamic composition is SELECT-only. It should be accounted for as read access, not inferred write access.
6. Configuration page count wrapper: it wraps known local SELECT query strings; no evidence that request input is interpolated as SQL.

## Remaining limitations before final privilege grants

- Resolve every dynamic SQL fragment inside PostgreSQL PL/pgSQL routines, including unqualified identifiers, EXECUTE format(), nested calls, and trigger reads. The earlier function-body text scan is not a complete parser.
- Inspect all migration/bootstrap scripts and non-app Python scripts for table/sequence/function access. Keep migration-only access separate from runtime.
- Map each resolved table operation to protected reachable routes and permission checks, including assistant/background execution paths.
- Confirm exact table and sequence privileges on a restored PostgreSQL 18 database with a non-owner, non-superuser runtime candidate.
- Verify SECURITY INVOKER trigger cross-table SELECT requirements and ordinary DML behavior after PUBLIC EXECUTE revocation.
- Do not infer blanket DELETE, TRUNCATE, TRIGGER, schema CREATE, or DDL rights from this scan.

## Status

- Dynamic Python SQL sites: manually traced to finite source-controlled identifier sets.
- Confirmed unqualified base-table names in reviewed dynamic sites: none.
- Purchasing section list query object map: extracted for all eight sections.
- Final runtime grant matrix: still incomplete pending routine-body dependencies, migrations/scripts, route reachability, and restored-database validation.
- Live database, runtime role, ACLs, DSN, application code, and server state: unchanged.
