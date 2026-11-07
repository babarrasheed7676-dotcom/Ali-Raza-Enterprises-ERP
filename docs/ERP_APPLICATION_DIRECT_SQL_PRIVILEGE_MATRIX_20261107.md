# Direct Python SQL Privilege Candidate Matrix — 7 November 2026

## Method and limitations

Static AST scan of Python files under app/. It inspects literal SQL passed to execute/executemany and constant portions of f-strings. It records schema-qualified table references in FROM/JOIN/INSERT/UPDATE/DELETE/TRUNCATE clauses. The known inventory.approve_stock_document routine call is excluded from table candidates. It does not resolve dynamic SQL, concatenated SQL, unqualified names, or every route reachability condition. These are candidate table references, not approved grants.

Files scanned: 41; qualified table-reference hits: 598; distinct candidate tables: 70.

The literal-SQL scan found no qualified DELETE FROM or TRUNCATE TABLE statements in these execute/executemany call arguments. This supports withholding broad DELETE/TRUNCATE from the runtime candidate, but it is not proof that no dynamic, concatenated, unqualified, or external path uses them.

| Candidate table | SQL operations observed | Source files |
|---|---|---|
| accounting.accounts | FROM (3 files), JOIN (1 files) | app/accounting/journal_service.py, app/accounting/report_service.py, app/main.py |
| accounting.journal_entries | FROM (3 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/accounting/journal_service.py, app/accounting/report_service.py, app/main.py |
| accounting.journal_lines | FROM (2 files), INSERT INTO (1 files), JOIN (1 files) | app/accounting/journal_service.py, app/accounting/report_service.py |
| configuration.config_approval_events | FROM (1 files), INSERT INTO (1 files) | app/configuration_service.py |
| configuration.config_audit_events | FROM (1 files), INSERT INTO (1 files) | app/configuration_service.py |
| configuration.config_versions | FROM (3 files), INSERT INTO (1 files), JOIN (2 files), UPDATE (1 files) | app/configuration_runtime_service.py, app/configuration_service.py, app/dyeing_draft_service.py, app/ownership_use_service.py, app/unit_conversion_service.py |
| core.accounting_periods | FROM (2 files), INSERT INTO (1 files), JOIN (1 files) | app/accounting/fiscal_year_service.py, app/accounting/journal_service.py, app/accounting/report_service.py, app/main.py |
| core.audit_log | INSERT INTO (1 files) | app/audit_service.py |
| core.company | FROM (1 files) | app/accounting/report_service.py |
| core.departments | FROM (4 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/production_master_service.py, app/production_service.py |
| core.document_sequences | UPDATE (1 files) | app/accounting/journal_service.py |
| core.fiscal_years | FROM (4 files), INSERT INTO (1 files), JOIN (2 files) | app/accounting/fiscal_year_service.py, app/accounting/journal_service.py, app/accounting/report_service.py, app/main.py |
| core.locations | JOIN (4 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/dyeing_draft_service.py, app/purchasing_service.py |
| core.permissions | JOIN (1 files) | app/authz.py |
| core.role_permissions | JOIN (1 files) | app/authz.py |
| core.roles | JOIN (2 files) | app/authz.py, app/configuration_service.py |
| core.user_roles | FROM (2 files) | app/authz.py, app/configuration_service.py |
| core.users | FROM (1 files), JOIN (1 files) | app/authz.py, app/ownership_use_service.py |
| inventory.batches | FROM (1 files), JOIN (3 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/dyeing_draft_service.py |
| inventory.locations | FROM (4 files), JOIN (2 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/dyeing_draft_service.py, app/packing_assortment_service.py, app/packing_service.py, app/purchasing_service.py |
| inventory.stock_balances | FROM (5 files), JOIN (4 files) | app/accounting/report_service.py, app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_master_service.py, app/dyeing_draft_service.py, app/packing_assortment_service.py, app/packing_random_draft_service.py, app/packing_service.py |
| inventory.stock_document_lines | FROM (1 files), INSERT INTO (1 files) | app/accounting/inventory_journal.py, app/purchasing_service.py |
| inventory.stock_documents | FROM (3 files), INSERT INTO (1 files) | app/accounting/inventory_journal.py, app/accounting/report_service.py, app/purchasing_service.py |
| inventory.transaction_types | FROM (2 files) | app/accounting/report_service.py, app/purchasing_service.py |
| master.brands | FROM (2 files), INSERT INTO (1 files), JOIN (4 files), UPDATE (1 files) | app/configuration_master_service.py, app/db.py, app/dyeing_draft_service.py, app/packing_assortment_service.py, app/packing_service.py |
| master.fiber_types | FROM (2 files), INSERT INTO (1 files), UPDATE (1 files) | app/configuration_master_service.py, app/db.py |
| master.item_categories | FROM (3 files), INSERT INTO (1 files), JOIN (3 files), UPDATE (1 files) | app/accounting/inventory_journal.py, app/accounting/report_service.py, app/configuration_master_service.py, app/db.py, app/dyeing_draft_service.py |
| master.item_variants | FROM (6 files), INSERT INTO (1 files), JOIN (11 files), UPDATE (1 files) | app/accounting/inventory_journal.py, app/baby_cone_draft_service.py, app/baby_cone_measurement_service.py, app/big_cone_draft_service.py, app/configuration_master_service.py, app/configuration_runtime_service.py, app/configuration_service.py, app/dyeing_draft_service.py, app/ownership_use_service.py, app/packing_assortment_service.py, app/packing_service.py, app/purchasing_service.py |
| master.items | FROM (3 files), INSERT INTO (1 files), JOIN (10 files), UPDATE (1 files) | app/accounting/inventory_journal.py, app/accounting/report_service.py, app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_master_service.py, app/configuration_service.py, app/db.py, app/dyeing_draft_service.py, app/ownership_use_service.py, app/packing_assortment_service.py, app/packing_service.py, app/purchasing_service.py |
| master.machines | FROM (5 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_master_service.py, app/production_master_service.py, app/production_service.py |
| master.ownership_types | FROM (3 files), JOIN (4 files) | app/accounting/report_service.py, app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_service.py, app/dyeing_draft_service.py, app/purchasing_service.py |
| master.parties | FROM (5 files), INSERT INTO (1 files), JOIN (6 files) | app/accounting/journal_service.py, app/accounting/report_service.py, app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/dyeing_draft_service.py, app/main.py, app/ownership_use_service.py, app/purchasing_service.py, app/supplier_service.py |
| master.party_financial_profiles | INSERT INTO (1 files), JOIN (1 files) | app/accounting/report_service.py, app/supplier_service.py |
| master.process_stages | FROM (5 files), JOIN (2 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_service.py, app/dyeing_draft_service.py, app/packing_assortment_service.py, app/packing_service.py, app/production_service.py |
| master.shade_categories | FROM (2 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/configuration_master_service.py, app/db.py |
| master.shades | FROM (3 files), INSERT INTO (1 files), JOIN (3 files), UPDATE (1 files) | app/configuration_master_service.py, app/db.py, app/dyeing_draft_service.py, app/packing_assortment_service.py, app/packing_service.py |
| master.units | FROM (6 files), INSERT INTO (1 files), JOIN (7 files), UPDATE (1 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/configuration_master_service.py, app/configuration_service.py, app/db.py, app/dyeing_draft_service.py, app/ownership_use_service.py, app/production_master_service.py, app/purchasing_service.py, app/unit_conversion_service.py |
| master.yarn_counts | FROM (2 files), INSERT INTO (1 files), UPDATE (1 files) | app/configuration_master_service.py, app/db.py |
| production.baby_cone_configuration_snapshots | FROM (1 files), INSERT INTO (1 files), JOIN (1 files) | app/baby_cone_measurement_service.py, app/configuration_runtime_service.py |
| production.baby_cone_cost_lines | FROM (1 files) | app/production_service.py |
| production.baby_cone_loss_lines | FROM (1 files) | app/production_service.py |
| production.baby_cone_material_lines | FROM (2 files) | app/baby_cone_draft_service.py, app/production_service.py |
| production.baby_cone_measurements | FROM (1 files), INSERT INTO (1 files) | app/configuration_runtime_service.py, app/production_service.py |
| production.baby_cone_orders | FROM (1 files), JOIN (3 files) | app/baby_cone_draft_service.py, app/baby_cone_measurement_service.py, app/configuration_runtime_service.py, app/production_service.py |
| production.baby_cone_output_lines | FROM (2 files), JOIN (2 files) | app/baby_cone_measurement_service.py, app/configuration_runtime_service.py, app/production_service.py |
| production.big_cone_material_lines | FROM (2 files), INSERT INTO (1 files) | app/big_cone_draft_service.py, app/production_service.py |
| production.big_cone_orders | FROM (2 files), INSERT INTO (1 files), JOIN (2 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/production_service.py |
| production.big_cone_output_lines | FROM (3 files), INSERT INTO (1 files) | app/baby_cone_draft_service.py, app/big_cone_draft_service.py, app/production_service.py |
| production.dyeing_consumption_lines | FROM (2 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/dyeing_draft_service.py, app/ownership_use_service.py, app/production_service.py |
| production.dyeing_material_lines | FROM (1 files), INSERT INTO (1 files), JOIN (1 files) | app/dyeing_draft_service.py |
| production.dyeing_orders | FROM (3 files), INSERT INTO (1 files), JOIN (3 files), UPDATE (1 files) | app/big_cone_draft_service.py, app/dyeing_draft_service.py, app/ownership_use_service.py, app/production_service.py |
| production.dyeing_output_lines | FROM (2 files), INSERT INTO (1 files), JOIN (1 files) | app/big_cone_draft_service.py, app/dyeing_draft_service.py |
| production.dyeing_unit_conversion_snapshots | INSERT INTO (1 files), JOIN (2 files) | app/dyeing_draft_service.py, app/production_service.py |
| production.ownership_use_requests | FROM (2 files), INSERT INTO (1 files), UPDATE (1 files) | app/main.py, app/ownership_use_service.py |
| production.packing_configuration_snapshots | FROM (1 files), INSERT INTO (1 files) | app/configuration_runtime_service.py, app/packing_service.py |
| production.packing_order_items | FROM (1 files), INSERT INTO (3 files) | app/packing_assortment_service.py, app/packing_random_draft_service.py, app/packing_service.py |
| production.packing_order_status_history | INSERT INTO (3 files) | app/packing_assortment_service.py, app/packing_random_draft_service.py, app/packing_service.py |
| production.packing_orders | FROM (3 files), INSERT INTO (3 files), JOIN (1 files) | app/ownership_use_service.py, app/packing_assortment_service.py, app/packing_random_draft_service.py, app/packing_service.py |
| production.packing_source_allocations | FROM (1 files), INSERT INTO (1 files), UPDATE (1 files) | app/ownership_use_service.py, app/packing_random_draft_service.py |
| production.production_executions | FROM (1 files) | app/production_service.py |
| production.production_orders | JOIN (1 files) | app/production_service.py |
| production.production_targets | FROM (1 files) | app/production_service.py |
| production.recipes | FROM (1 files) | app/production_service.py |
| purchasing.purchase_configuration_snapshots | INSERT INTO (1 files) | app/configuration_runtime_service.py |
| purchasing.purchase_order_lines | FROM (1 files), UPDATE (1 files) | app/purchasing_service.py |
| purchasing.purchase_orders | FROM (2 files), JOIN (1 files) | app/accounting/report_service.py, app/purchasing_service.py |
| purchasing.purchase_receipt_lines | FROM (1 files), INSERT INTO (1 files), JOIN (1 files) | app/purchasing_service.py |
| purchasing.purchase_receipts | FROM (2 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/accounting/report_service.py, app/purchasing_service.py |
| purchasing.purchase_return_lines | FROM (1 files), INSERT INTO (1 files) | app/purchasing_service.py |
| purchasing.purchase_returns | FROM (2 files), INSERT INTO (1 files), JOIN (1 files), UPDATE (1 files) | app/accounting/report_service.py, app/purchasing_service.py |
