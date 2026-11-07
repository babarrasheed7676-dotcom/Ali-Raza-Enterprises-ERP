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

## Backup archive extraction integrity check

The six valid custom-format archives listed above were each passed through PostgreSQL 18.6 `pg_restore --schema-only --file NUL` and `pg_restore --data-only --file NUL`. **All 12 extraction checks returned exit code 0** (schema and data extraction for each of six archives). Output was discarded to the Windows NUL device; no extracted schema/data files were created, no restore connection was opened, and no database was modified. This verifies archive readability/decompression for the selected schema and data sections, but it is not a full restore test or row-level application integrity validation.

The zero-byte `ali_raza_erp_pre_config_supersession_20261105_204110.dump` remains excluded and failed the basic archive/TOC review.

## Backup schema inventory versus current catalog

A schema-only extraction from each of the six readable archives was parsed locally and compared with the current 130 application base tables from a consistent read-only catalog snapshot. Temporary extracted SQL was deleted after counting; no raw schema dump was added to the repository.

| Verified archive | CREATE TABLE entries | Current tables absent from that archive |
|---|---:|---:|
| `ali_raza_erp_pre_configuration_20261105.dump` | 120 | 10 |
| `ali_raza_erp_pre_config_approval_20261105.dump` | 123 | 7 |
| `ali_raza_erp_pre_packing_config_snapshot_20261105.dump` | 124 | 6 |
| `ali_raza_erp_pre_packing_phase2g_20261105.dump` | 123 | 7 |
| `ali_raza_erp_pre_packing_snapshot_guard_20261105.dump` | 125 | 5 |
| `ali_raza_erp_pre_purchasing_config_snapshot_20261105.dump` | 125 | 5 |

The two latest 125-table snapshots are each missing the same five current relations:

- `purchasing.purchase_configuration_snapshots` — migration `20261105_008_purchasing_configuration_snapshots.sql`
- `production.baby_cone_configuration_snapshots` — migration `20261106_009_baby_cone_configuration_snapshots.sql`
- `production.baby_cone_measurements` — migration `20261106_010_baby_cone_measurement_drafts.sql`
- `production.ownership_use_requests` — migration `20261106_011_ownership_use_requests.sql`
- `production.dyeing_unit_conversion_snapshots` — migration `20261107_018_dyeing_unit_conversion_snapshots.sql`

For these latest snapshots, the remaining 125 application table definitions match the current catalog set exactly; there were no archive-only application tables in the comparison. This gives a concrete migration boundary for the five listed objects and establishes a reproducible historical schema starting point, subject to an approved isolated restore test. Earlier archives have earlier table counts and should not be mixed as if they were interchangeable full-current snapshots.

The table comparison is limited to application base-table names and does not prove that every function, trigger, extension, owner, ACL, or data row is identical to the current live database. The six archive extraction checks succeeded, but no restore test has been performed.

## Migration tracking ledger check

A read-only catalog search across all application schemas found no base table whose name matches `%migration%`, `%schema_version%`, or `%alembic%`. The repository also has no Alembic migration runner/configuration in the active files scanned, and the README explicitly says SQL migrations are not run automatically. Therefore the database does not expose a migration ledger that can reliably prove which numbered scripts were applied or in what order.

Do not infer applied migration status solely from the current table count or backup filename. For a future staging rebuild, record each migration filename, SHA-256 hash, execution timestamp, operator, result, and post-migration object checks in an external deployment manifest or a formally approved migration ledger. Create a database-resident ledger only through a reviewed migration and explicit approval; no such table was added during this audit.

## Sequence inventory reconciliation

The latest 125-table archive contains **123 distinct application sequence objects** in its TOC. The current live catalog contains **128 application sequences**. The five current-only sequence objects are exactly the identity sequences for the five tables introduced after that archive:

- `purchasing.purchase_configuration_snapshots_id_seq`
- `production.baby_cone_configuration_snapshots_id_seq`
- `production.baby_cone_measurements_id_seq`
- `production.ownership_use_requests_id_seq`
- `production.dyeing_unit_conversion_snapshots_id_seq`

No archive-only application sequence was found. This sequence delta matches the five-table delta and supports the identified migration boundary. It does not establish which runtime role should receive USAGE/SELECT/UPDATE; those privileges must be traced to actual insert/default behavior and validated on staging.
