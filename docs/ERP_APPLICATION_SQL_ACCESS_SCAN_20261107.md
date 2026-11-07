# ERP Application SQL Access Scan — 7 November 2026

## Scope

A static, read-only scan of Python files under `app/` in the Git mirror. The scanner inspected literal SQL passed to `execute` and `executemany`, including constant portions of f-strings, and looked for schema-qualified names in FROM, JOIN, INSERT INTO, UPDATE, DELETE FROM, and TRUNCATE clauses.

- Python files scanned: 41
- SQL reference hits: 600
- Distinct schema-qualified candidates: 71
- No application files or database objects were changed by the scan.

## Candidate objects by schema

These are code-reference candidates, not a final grant list. Some candidates may be false positives (for example, a routine name may appear in a FROM-like context); dynamic SQL, unqualified names, stored routine dependencies, trigger execution, and non-Python paths are not fully covered.

| Schema | Candidate names |
|---|---|
| accounting | accounts; journal_entries; journal_lines |
| configuration | config_approval_events; config_audit_events; config_versions |
| core | accounting_periods; audit_log; company; departments; document_sequences; fiscal_years; locations; permissions; role_permissions; roles; user_roles; users |
| inventory | approve_stock_document*; batches; locations; stock_balances; stock_document_lines; stock_documents; transaction_types |
| master | brands; fiber_types; item_categories; item_variants; items; machines; ownership_types; parties; party_financial_profiles; process_stages; shade_categories; shades; units; yarn_counts |
| production | baby_cone_configuration_snapshots; baby_cone_cost_lines; baby_cone_loss_lines; baby_cone_material_lines; baby_cone_measurements; baby_cone_orders; baby_cone_output_lines; big_cone_material_lines; big_cone_orders; big_cone_output_lines; dyeing_consumption_lines; dyeing_material_lines; dyeing_orders; dyeing_output_lines; dyeing_unit_conversion_snapshots; ownership_use_requests; packing_configuration_snapshots; packing_order_items; packing_order_status_history; packing_orders; packing_source_allocations; production_executions; production_orders; production_targets; recipes |
| purchasing | purchase_configuration_snapshots; purchase_order_lines; purchase_orders; purchase_receipt_lines; purchase_receipts; purchase_return_lines; purchase_returns |
| sales | No schema-qualified sales table reference was found by this limited scan. This is not proof that sales tables are unused; inspect route imports, dynamic SQL, and database routines separately. |

`* approve_stock_document` is a routine-name candidate and must be verified against the catalog, not treated as a table grant target.

## Important interpretation limits

1. A SQL string reference does not establish that a route is reachable, that a write is currently used, or that the runtime needs the same privilege on every row/table.
2. The scan does not fully resolve dynamic SQL, SQL assembled across variables, unqualified object references, views, trigger bodies, PL/pgSQL dependencies, or external scripts.
3. It does not prove company scoping, tenant isolation, transaction boundaries, or lifecycle safety.
4. Trigger-only routines must not be granted to the application role merely because they exist. Directly invoked routines need separate EXECUTE analysis.
5. Sequence calls and implicit identity/default sequence use need their own map. Ownership/sequence privileges must not be inferred from this scan.
6. `SELECT` references inside subqueries and joins are captured as candidates; this report does not classify every individual statement into a complete per-table privilege policy.

## Next analysis required

- Review every write statement by route/service and classify INSERT, UPDATE, DELETE, and any sequence use.
- Resolve the 71 candidates against live catalog object types and remove non-table/routine false positives.
- Inspect all database routines and trigger definitions to identify indirect writes and execution dependencies.
- Search non-Python application, migration, script, and assistant paths.
- Build the candidate runtime-role grant matrix only after these checks, then validate on a restored database copy.

## Status

This is an intermediate source-code inventory only. It does not authorize or implement a runtime role, grants, ownership transfer, DSN switch, or any live database change.
