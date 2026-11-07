# ERP Catalog Tables Without Active Source References ? 8 November 2026

## Scope and interpretation

Read-only comparison of the 130 live application base tables with 147 active source files across app/, database/migrations/, tests/, plus create_babar_admin_local.py. The scan searched for schema-qualified table names. It then cross-checked the stored-routine dependency map extracted from all 46 routine definitions. No live data, role, ACL, schema, code, DSN, or server state was changed.

A missing qualified reference is a review flag, not proof that a table is obsolete. A table may be referenced through unqualified SQL, dynamic SQL not captured by the scan, triggers, nested functions, ORM/driver behavior, external scripts, or future module plans. Do not drop tables or revoke permissions based on this report.

- Catalog application base tables: **130**.
- Active source files scanned: **147**.
- Tables with no schema-qualified reference in those active source files: **51**.
- Of those, referenced by inspected stored routines: **10**.
- Of those, not referenced by the inspected stored-routine matrix either: **41**.

## No active direct source reference, but referenced by stored routines

These objects have a stored-routine dependency; their runtime relevance depends on whether the owning routine/trigger path is reachable and enabled.
- inventory.stock_ledger
- inventory.stock_reservation_lines
- inventory.stock_reservations
- production.packing_fg_transfers
- production.packing_labour
- production.packing_material_consumption
- sales.dispatch_lines
- sales.dispatches
- sales.sales_order_lines
- sales.sales_orders

## No qualified reference in active app/migration/test files or stored-routine matrix

These are candidates for module/schema lifecycle review only. They may be reserved for planned functionality, historical migrations, or external workflows. Do not classify as deletable without owner confirmation and full reference checks.
- core.system_settings
- inventory.opening_stock
- inventory.stock_adjustments
- inventory.stock_transfers
- production.big_cone_cost_lines
- production.big_cone_loss_lines
- production.dyeing_rework_material_lines
- production.dyeing_rework_orders
- production.machine_capacities
- production.machine_downtime
- production.nalki_cost_lines
- production.nalki_loss_lines
- production.nalki_material_lines
- production.outside_dyeing_consumable_lines
- production.outside_dyeing_cost_lines
- production.outside_dyeing_loss_lines
- production.outside_dyeing_material_lines
- production.outside_dyeing_orders
- production.outside_dyeing_return_lines
- production.outside_labeling_cost_lines
- production.outside_labeling_label_lines
- production.outside_labeling_loss_lines
- production.outside_labeling_nalki_lines
- production.packing_completions
- production.packing_material_returns
- production.packing_quality_checks
- production.packing_wastage
- production.production_execution_lines
- production.production_execution_status_history
- production.production_material_consumptions
- production.production_order_lines
- production.production_order_status_history
- production.production_outputs
- production.production_quality_checks
- production.recipe_components
- production.recipe_process_steps
- production.rewinding_material_lines
- production.rewinding_orders
- production.rewinding_output_lines
- purchasing.purchase_landed_cost_lines
- purchasing.quality_inspection_dispositions

## Safe next steps

1. Check the owning module status and current route/service coverage for each object.
2. Search for unqualified references and external scripts before any ACL decision.
3. Check foreign keys, triggers, views, routines, and sequence dependencies from PostgreSQL catalogs.
4. For planned features, retain schema objects but keep them outside runtime grants until the feature has a protected route.
5. Any eventual cleanup or permission removal requires a separate backup, dependency review, staging test, and explicit approval.

## Status

Read-only inventory and source-reference comparison complete. No schema objects or permissions were changed.
