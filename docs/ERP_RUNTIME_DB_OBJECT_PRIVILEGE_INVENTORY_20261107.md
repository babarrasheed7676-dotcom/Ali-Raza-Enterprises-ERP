# ERP Runtime DB Object and Privilege Inventory — 7 November 2026

## Scope and safety

Read-only PostgreSQL catalog inspection using the application's currently configured connection. No database writes, role changes, grants, ownership changes, DSN changes, application runtime changes, or server restarts were performed. The temporary inspection script was removed after execution.

This is a database-object/authority inventory, not yet a complete application least-privilege grant matrix. The codebase contains multiple module services and dynamically composed SQL; a safe candidate runtime role must not be generated from broad text matching alone.

## Verified connection identity

- Runtime connection identity: `postgres` (also `session_user`).
- Role is a superuser and has the previously verified elevated role attributes.
- All inspected application schemas and all inspected table/index/sequence objects are owned by `postgres`.
- Consequently, `has_table_privilege` and `has_sequence_privilege` report broad access. These effective checks must not be mistaken for a least-privilege explicit ACL design.

## Application schema object inventory

Catalog counts from `pg_class`:

| Schema | Tables (`r`) | Indexes (`i`) | Sequences (`S`) | Owner |
|---|---:|---:|---:|---|
| accounting | 3 | 14 | 3 | postgres |
| configuration | 3 | 7 | 3 | postgres |
| core | 13 | 26 | 11 | postgres |
| inventory | 12 | 35 | 12 | postgres |
| master | 14 | 33 | 14 | postgres |
| production | 67 | 316 | 67 | postgres |
| purchasing | 14 | 58 | 14 | postgres |
| sales | 4 | 21 | 4 | postgres |
| **Total** | **130** | **510** | **128** | **postgres** |

No views, materialized views, or foreign tables appeared in the inspected application schemas in this catalog result. The reported relation kinds were tables, indexes, and sequences.

## Schema privileges and default privileges

- The connected runtime role has effective USAGE and CREATE on all eight application schemas.
- No rows were returned by `pg_default_acl` for default-privilege overrides.
- The runtime role is superuser and schema owner; therefore, effective schema access is not evidence of a safe explicit grant set.
- The connected role has effective USAGE, SELECT, and UPDATE on every inspected sequence. This is owner/superuser-level access, not a proposed runtime grant set.
- The `information_schema` usage-privilege view returned no sequence privilege rows for this role; effective access above comes from elevated ownership/superuser authority.

## Routine/function inventory

The catalog returned 46 routines in the application schemas. All are owned by `postgres`, all report EXECUTE access for the current connection, and none were marked SECURITY DEFINER.

| Schema | Routine count |
|---|---:|
| accounting | 3 |
| configuration | 0 |
| core | 1 |
| inventory | 5 |
| master | 0 |
| production | 31 |
| purchasing | 1 |
| sales | 5 |
| **Total** | **46** |

The list includes trigger functions and business routines such as stock posting/reservation, packing-cost calculation, Baby Cone/Big Cone/Dyeing guards, and sales dispatch/order routines. Runtime EXECUTE requirements must be separated from trigger invocation and migration/administrative ownership before designing grants.

## Privilege exposure confirmed

- Runtime can CREATE in every application schema.
- Runtime owns every inspected application table, index, and sequence.
- Runtime effectively has SELECT, INSERT, UPDATE, DELETE, TRUNCATE, and TRIGGER authority on every inspected table.
- Runtime effectively has USAGE, SELECT, and UPDATE on every inspected sequence.
- Runtime can execute all 46 inspected routines.
- No SECURITY DEFINER routines and no default-ACL rows were found in the inspected schemas.

This is consistent with the previously documented critical least-privilege gap. Application permissions and CSRF protection do not contain database-superuser authority. Database triggers cannot be treated as an independent security boundary while the web process runs as the object-owning superuser.

## Next required analysis — still design-only

1. Build a query-by-query table/sequence/routine access matrix from every application service, route, assistant endpoint, report, and background path. Classify SELECT/INSERT/UPDATE/DELETE and sequence use separately.
2. Inspect trigger definitions and function dependencies to distinguish functions called directly by application SQL from trigger-only functions.
3. Identify any SQL paths that rely on ownership, schema CREATE, TRUNCATE, trigger administration, or implicit sequence access; replace those dependencies before candidate grants are designed.
4. Separate the migration/owner identity from the runtime identity. The runtime identity must not own objects, be superuser, create roles/databases, bypass RLS, or have DDL/TRUNCATE/TRIGGER rights.
5. Validate a candidate role only on a restored database copy. Exercise authentication, dashboard, purchasing, production, inventory, accounting, reports, assistant, audit logging, transaction rollback, and sequence generation.
6. Prove that destructive/administrative operations are denied before any staged DSN change is considered.
7. Keep the live role, password, DSN, grants, ownership, and schema unchanged until a separate explicitly approved migration and rollback plan exists.

## Status

- Catalog inventory: complete, read-only.
- Application query-to-privilege matrix: not complete.
- Candidate runtime-role SQL: not generated; exact grants are not yet proven.
- Live database and runtime configuration: unchanged.
- Baby Cone DRAFT guard proposal: remains unexecuted.
