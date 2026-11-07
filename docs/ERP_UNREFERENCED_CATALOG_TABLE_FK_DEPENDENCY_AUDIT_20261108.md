# Unreferenced Catalog Tables — Foreign-Key Dependency Audit — 8 November 2026

## Scope

Read-only PostgreSQL catalog inspection of the 41 relations previously flagged for having no schema-qualified reference in the 147 active source files and no match in the inspected stored-routine dependency matrix. The live catalog was queried in a transaction marked READ ONLY. No table, row, role, ACL, schema, application file, DSN, or server process was changed.

## Results

- Target relations checked: **41**.
- Relations with at least one inbound or outbound foreign-key relationship: **40**.
- Relations with no foreign-key relationship: **1 — core.system_settings**.
- Distinct foreign-key constraints touching the 41 target relations: **221**.
- Non-internal triggers directly attached to the 41 target relations: **0**.
- View/rule dependencies recorded through pg_rewrite for the 41 target relations: **0**.

The zero trigger and view counts refer only to direct catalog attachments/dependencies captured by these specific catalog queries. They do not prove the relations are unused: foreign keys, external tools, unqualified SQL, application plans, and other dependencies still matter.

## What the foreign keys demonstrate

The flagged relations are structurally integrated into the ERP schema. Representative dependency paths include:

- Inventory opening stock, adjustments and transfers link to company/users, batches, locations, item variants, ownership types, parties and process stages.
- Production cost/loss/material tables link to their production orders, batches, item variants, units, parties, machines, recipes, and execution records.
- Outside dyeing and labeling tables link to order headers, material/return lines, batches, item variants, shades, units, locations and ownership references.
- Packing completion, material-return, quality and wastage tables link to packing orders/order items, users, locations, item variants and units.
- Production execution, order, output and material-consumption tables link to execution/order headers and inventory/master dimensions.
- Rewinding order/material/output tables link to departments, users, machines, units, batches, locations, item variants and ownership/process-stage dimensions.
- Purchase landed-cost lines link to landed-cost headers and purchase receipt lines; quality-inspection dispositions link to inspection records, users and inventory locations.

## Per-relation foreign-key edge counts

Counts include inbound and outbound FK constraints touching each target relation. A constraint connecting two target relations is counted for each endpoint in this per-relation view; the total of distinct constraints across the set is 221.

| Relation | FK edges |
|---|---:|
| core.system_settings | 0 |
| inventory.opening_stock | 9 |
| inventory.stock_adjustments | 8 |
| inventory.stock_transfers | 10 |
| production.big_cone_cost_lines | 2 |
| production.big_cone_loss_lines | 4 |
| production.dyeing_rework_material_lines | 5 |
| production.dyeing_rework_orders | 15 |
| production.machine_capacities | 2 |
| production.machine_downtime | 5 |
| production.nalki_cost_lines | 3 |
| production.nalki_loss_lines | 4 |
| production.nalki_material_lines | 8 |
| production.outside_dyeing_consumable_lines | 4 |
| production.outside_dyeing_cost_lines | 3 |
| production.outside_dyeing_loss_lines | 4 |
| production.outside_dyeing_material_lines | 8 |
| production.outside_dyeing_orders | 12 |
| production.outside_dyeing_return_lines | 9 |
| production.outside_labeling_cost_lines | 3 |
| production.outside_labeling_label_lines | 6 |
| production.outside_labeling_loss_lines | 7 |
| production.outside_labeling_nalki_lines | 8 |
| production.packing_completions | 3 |
| production.packing_material_returns | 5 |
| production.packing_quality_checks | 4 |
| production.packing_wastage | 4 |
| production.production_execution_lines | 8 |
| production.production_execution_status_history | 2 |
| production.production_material_consumptions | 8 |
| production.production_order_lines | 8 |
| production.production_order_status_history | 2 |
| production.production_outputs | 8 |
| production.production_quality_checks | 4 |
| production.recipe_components | 3 |
| production.recipe_process_steps | 1 |
| production.rewinding_material_lines | 8 |
| production.rewinding_orders | 11 |
| production.rewinding_output_lines | 8 |
| purchasing.purchase_landed_cost_lines | 2 |
| purchasing.quality_inspection_dispositions | 3 |

## Permission and lifecycle implications

1. **Do not drop these relations based on source-reference absence.** 40 of 41 are tied into referential integrity; 221 FK constraints touch this set.
2. **Do not grant runtime access merely because a relation has foreign keys.** Referential integrity proves structural relationships, not route reachability or application need.
3. **Keep planned and dormant production workflows out of the runtime grant set** until a protected route and service path are implemented and tested.
4. **core.system_settings remains a separate review item.** It has no FK edge, direct qualified source reference, or inspected routine dependency in the current evidence set. This still does not prove it is safe to remove; inspect migration history, settings conventions, deployment scripts and future configuration plans first.
5. The current migration directory yielded no table-name hits. Remaining safe review is to inspect schema-definition/bootstrap artifacts, deployment scripts outside database/migrations, and feature-roadmap dependencies before final privilege decisions.

## Migration-history name scan

A second read-only source scan searched all 41 table names as whole identifiers (not only schema-qualified names) across 31 files under database/migrations with .sql, .py, and .md extensions. **No bare-name matches were found for any of the 41 relations.** This means the current migration directory does not provide a positive migration-file reference for these relations under the scanned file types. It does not prove the tables were never created or are unused: they may have been created by another bootstrap path, imported schema snapshot, manual SQL, external deployment artifact, or older source no longer present in the directory.

## Status

Catalog FK dependency and migration-history name checks complete for all 41 flagged relations. Live database remained read-only; no schema cleanup or privilege changes performed.

## Database-backup archive provenance check

The migration directory did not contain names for these 41 relations, so the seven custom-format PostgreSQL archives under database/backups were inspected with PostgreSQL 18.6 `pg_restore --list` only. No archive was restored and no data was extracted or modified.

Six valid archives each contain both a TABLE definition entry and a TABLE DATA archive entry for **all 41 of the 41 flagged relations**:

- `ali_raza_erp_pre_configuration_20261105.dump`
- `ali_raza_erp_pre_config_approval_20261105.dump`
- `ali_raza_erp_pre_packing_config_snapshot_20261105.dump`
- `ali_raza_erp_pre_packing_phase2g_20261105.dump`
- `ali_raza_erp_pre_packing_snapshot_guard_20261105.dump`
- `ali_raza_erp_pre_purchasing_config_snapshot_20261105.dump`

The archive named `ali_raza_erp_pre_config_supersession_20261105_204110.dump` had no readable TOC entries and a reported size of approximately 0.0 MB; it is not counted as evidence of a valid snapshot and should be separately checked for truncation before anyone relies on it.

This establishes that the 41 tables are part of multiple November 5, 2026 database backup snapshots, despite the absence of matching names in the current migration directory and active source scan. `TABLE DATA` entries mean the archives include data sections for these relations; this TOC-only inspection does **not** establish that any given table contains non-zero rows.

**Conclusion updated:** the 41 relations are not safe deletion candidates. Their absence from the current source/migration scan is a source-coverage or workflow-activation question, not evidence that the database objects are accidental. Retain them pending schema/bootstrap provenance and business workflow reconciliation. Do not widen runtime grants solely because backup entries exist.

## Source-reference correction from expanded repository scan

Follow-up source review found five active dynamic application references among the 41 relations listed above: production.dyeing_rework_orders, production.machine_capacities, production.machine_downtime, production.rewinding_orders, and production.outside_dyeing_orders. Their current source paths use fixed internal identifier tuples and SELECT-only checks/dashboard summaries. The remaining 36 relations had no application-code name hit in the expanded 177-file scan. This does not change the catalog FK counts or the six backup archives containing TABLE and TABLE DATA entries for all 41 relations. It does change the earlier interpretation: these are not 41 wholly unreferenced tables; five are active read dependencies and 36 remain unreferenced by current application code in the expanded scan.
