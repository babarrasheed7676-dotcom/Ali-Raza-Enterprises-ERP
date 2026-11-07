# ERP Base Schema and Bootstrap Provenance Gap Audit — 8 November 2026

## Purpose

Determine whether the current repository contains a reproducible baseline schema definition for the pre-existing ERP database, especially the 41 catalog relations that have no schema-qualified literal references in the original source scan. This is a read-only repository and backup-archive review. No database restore, DDL, role/ACL change, application edit, DSN change, or server restart was performed.

## Evidence reviewed

1. Current repository text/source scan: 177 files across Python, SQL, Markdown, text, JSON, TOML, YAML and batch extensions. Virtual environment, backup directories, logs and database backup archives were excluded from the active-source scan.
2. Database migration directory: 31 SQL/Python/Markdown files were enumerated. The tracked migration sequence begins with `20261105_001_general_ledger.sql`, followed by configuration, packing, purchasing, Baby Cone, ownership-use and dyeing conversion/traceability migrations through `20261107_031_dyeing_consumption_source_yarn_lineage.sql`.
3. Schema-creation search: current source contains the incremental `CREATE TABLE` statements in the listed migrations (accounting journal, configuration, packing/configuration snapshots, ownership-use, Baby Cone measurement and dyeing conversion snapshots). No single baseline schema/bootstrap script defining the pre-existing 8 application schemas and their original 130 tables was found in the 177-file active-source scan.
4. README states that this Python/FastAPI foundation connects to an existing `ali_raza_erp` database, does not automatically run SQL migrations, and does not modify the existing ERP schema or test data. This corroborates that the base schema predates the tracked incremental migrations.
5. `scripts/check_environment.py` is a dependency diagnostic; `scripts/read_only_purchase_schema_audit.py` is a read-only catalog query; `create_babar_admin_local.py` creates a user/role assignment and does not bootstrap the base schema.
6. Seven custom-format backup archives exist under `database/backups`. Six valid archives contain both TABLE and TABLE DATA archive entries for all 41 flagged relations. The archive `ali_raza_erp_pre_config_supersession_20261105_204110.dump` is zero bytes and has no usable TOC; it is not a valid restore point.

## Findings

- The repository currently has incremental migrations, but no discoverable versioned baseline schema source for the original ERP database.
- The six valid November 5, 2026 archives provide historical database snapshots containing the 41 reviewed relations. A `pg_restore --list` check proves the archive entries exist; it does not prove non-zero row counts or successful restore integrity.
- Five of the 41 relations have since been confirmed as active application read dependencies through fixed dynamic table maps: `production.dyeing_rework_orders`, `production.machine_capacities`, `production.machine_downtime`, `production.rewinding_orders`, and `production.outside_dyeing_orders`.
- The remaining 36 relations had no application-code name hit in the expanded 177-file scan. Their FK edges and backup archive presence mean they must not be treated as accidental or deletable.
- The zero-byte supersession archive must not be used as a backup or restore source. Retain its filename only as a failed/empty artifact until a human decides whether to archive or remove it.

## Security and deployment implications

1. A fresh database cannot be reliably reconstructed from the currently tracked migration directory alone. The current migration set assumes a pre-existing schema and must not be presented as a complete database bootstrap.
2. Do not attempt to recreate the schema from the six backup archives by restoring into the live database. Any restore validation must use a separately approved, isolated staging database and a verified archive.
3. Before publishing a baseline schema export to the public GitHub repository, inspect it for role names, ACLs, function bodies, extension assumptions, comments, security-sensitive object names, and any embedded environment-specific configuration. Do not publish passwords, database dumps, user data, or private records.
4. The least-privilege runtime role proposal must remain separate from schema ownership/bootstrap privileges. Runtime access must not receive DDL or schema CREATE rights.
5. Keep the zero-byte archive excluded from backup inventory counts and backup selection until repaired or replaced with a verified archive.

## Recommended next controlled steps

- Obtain explicit approval before creating an isolated staging database or performing any restore.
- In that isolated staging environment, restore one verified November 5 archive, validate the complete schema and row-level integrity, then capture a sanitized baseline schema-only export.
- Compare that export against the current incremental migrations to identify the precise baseline/migration boundary and document the required PostgreSQL version/extensions.
- Create a reproducible baseline migration only after that comparison and review; do not invent missing DDL from table names or foreign keys.
- Keep all staging role/ACL experiments separate from the live `postgres` runtime connection and do not change the live DSN without separate approval.

## Status

Repository bootstrap provenance gap documented. All actions in this audit were read-only. Live ERP, roles, ACLs, schema, data, application files and server process remain unchanged.

## Live database row-count cross-check

A consistent PostgreSQL `REPEATABLE READ, READ ONLY` snapshot confirmed that all 41 catalog source-gap relations currently contain zero rows. A separate snapshot of the ten stored-routine-only dependencies found nine non-empty relations: inventory.stock_ledger (12), inventory.stock_reservation_lines (2), inventory.stock_reservations (2), production.packing_fg_transfers (2), production.packing_labour (2), sales.dispatch_lines (3), sales.dispatches (3), sales.sales_order_lines (2), and sales.sales_orders (2). `production.packing_material_consumption` returned zero rows. These are counts only; no record contents were retrieved.

This distinction matters for backup/provenance decisions: the 41 source-gap relations are empty in the live database at the check snapshot, while several routine-only dependencies contain existing ERP records and must be preserved even where their owning module currently lacks a protected application route.
