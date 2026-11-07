# ERP Staging Restore and Migration Rehearsal Plan — 8 November 2026

## Status and safety boundary

This is a proposed staging-only runbook. It has not been executed. No database was created/restored, no migration was run, and no live role, ACL, schema, record, DSN or server process was changed. Creating an isolated staging database and restoring a backup still requires separate explicit approval.

## Best current archive candidate

| Attribute | Verified value |
|---|---|
| Archive | `database/backups/ali_raza_erp_pre_purchasing_config_snapshot_20261105.dump` |
| Size | 1,004,115 bytes |
| Last-write timestamp | 5 Nov 2026, 10:52:42 PM |
| SHA-256 | `6BDE8AD211B0E2935F0F6C37259B5FC0A26711A543DD9DFEF3D298AD0F18C9EB` |
| PostgreSQL archive TOC entries | 1,631 |
| Application base tables in schema-only extraction | 125 |
| Schema-only extraction | Exit code 0 |
| Data-only extraction | Exit code 0 |

The archive's schema/data extraction was directed to the Windows NUL device; no data files were retained. This validates archive readability/decompression, not a complete restore.

The archive's timestamp precedes the `20261105_008_purchasing_configuration_snapshots.sql` file timestamp by 34 seconds. Its 125 application table definitions match the current catalog except for the five relations introduced by migrations 008, 009, 010, 011 and 018. This is consistent with a pre-008 baseline, but timestamps and object comparison do not replace a migration ledger.

## Current schema comparison

Current application base tables: **130** across eight application schemas.

The latest archive has 125 application base-table definitions. The five current tables absent from that archive are:

1. `purchasing.purchase_configuration_snapshots` — migration 008.
2. `production.baby_cone_configuration_snapshots` — migration 009.
3. `production.baby_cone_measurements` — migration 010.
4. `production.ownership_use_requests` — migration 011.
5. `production.dyeing_unit_conversion_snapshots` — migration 018.

No archive-only application base table was found in the comparison. The 125-table match does not establish that functions, triggers, indexes, owners, ACLs, extensions or all data rows are identical.

## Rehearsal sequence — only after approval

### Gate 1 — isolated target

- Confirm PostgreSQL 18.6 and the required extension availability.
- Create a dedicated staging database with an unmistakable staging-only name and a separate staging owner/credential.
- Verify the connection target with `current_database()`, server address and current role before any restore.
- Confirm that no connection string or command points to the live `ali_raza_erp` database.
- Keep the staging database isolated from factory users and the live ERP server.

### Gate 2 — restore and baseline validation

- Verify the archive SHA-256 against the value above.
- Restore into the isolated staging database only, after reviewing owner/ACL/extension restore flags.
- Verify eight expected application schemas and the 125 baseline application tables.
- Compare critical routines, triggers, sequences, constraints and indexes with the archive TOC and current catalog inventory.
- Run referential-integrity and row-count checks without copying or exposing user credentials.

### Gate 3 — migration boundary

- Do not replay migrations 001–007 automatically. First verify their objects and definitions are already present in the restored baseline.
- Evaluate migrations 008–031 in ascending filename order against the restored staging schema.
- Check each migration's preconditions and postconditions before proceeding to the next file.
- Record the exact SHA-256, start/end timestamp, operator, execution result and verification query results for every applied migration.
- Create/use a migration ledger in staging only after its design is reviewed. The current live database has no migration ledger.
- Never rerun a migration simply because its ledger entry is missing. The scripts contain 12 plain CREATE TABLE statements and several object replacement/drop operations; all are transaction-wrapped but are not generally replay-safe.

### Gate 4 — final schema validation

- Confirm the five expected tables are present and the total application base-table count is 130.
- Compare all 46 application routines, 44 triggers, 128 sequences, constraints and indexes with the current read-only catalog inventory.
- Verify all five dynamic production SELECT dependencies and the 94-relation candidate matrix.
- Confirm the 41 source-gap relations remain empty unless a test explicitly creates staging-only records.
- Validate the one-godown/process-stage mapping and preserve existing posted stock/packing records in the restored dataset.

### Gate 5 — least-privilege rehearsal

- Create a staging-only non-superuser candidate role; do not reuse or alter the live `postgres` role.
- Apply only reviewed schema USAGE, per-table operation, sequence and routine EXECUTE privileges.
- Test protected purchasing approval/posting, accounting journal actions, configuration approvals, production draft/read paths and trigger invocation under the candidate role.
- Confirm dormant Sales & Dispatch and packing FG-transfer routes remain unavailable and do not receive runtime routine EXECUTE.
- Test trigger SECURITY INVOKER cross-table reads after the staging-only PUBLIC EXECUTE changes.
- Keep the final grants, rollback SQL and observed failures in a separate reviewed artifact.

## Migration file cautions

- The 31 current SQL migration files all contain explicit BEGIN/COMMIT.
- Twelve CREATE TABLE statements are plain, not IF NOT EXISTS.
- Migration 012 drops two triggers and a function before replacing them; migration 019 drops a constraint; migration 024 drops two triggers before replacing them.
- No DROP TABLE, TRUNCATE TABLE or DELETE FROM statement was found in the current migration set.
- Use the SHA-256 manifest `ERP_MIGRATION_FILE_INTEGRITY_MANIFEST_20261108.md` as the exact file baseline; recompute hashes before rehearsal.

## Stop conditions

Stop without proceeding if the archive hash differs, any required extension is missing, a migration precondition fails, the staging connection resolves to the live database, the expected baseline table inventory differs, or a trigger/constraint definition does not match. Do not attempt automatic repair or continue past a failed migration.

## Live-system guarantee

This runbook does not authorize a restore, migration, role creation, grant/revoke, ownership change, DSN change, server restart, or live-data mutation. Each such operation requires explicit approval after its exact target and rollback path are shown.
