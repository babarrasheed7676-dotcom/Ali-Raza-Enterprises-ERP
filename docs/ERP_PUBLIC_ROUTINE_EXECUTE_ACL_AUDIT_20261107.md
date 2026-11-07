# ERP PUBLIC Routine EXECUTE ACL Audit — 7 November 2026

## Scope and safety

Read-only inspection of PostgreSQL ACL catalogs for the eight application schemas. No grants, revokes, role attributes, ownership, DSN, application code, or server state were changed.

## Verified ACL findings

| Object class | PUBLIC grants found |
|---|---:|
| Application schemas | 0 |
| Application tables/views | 0 |
| Application sequences | 0 |
| Application routines | 46 EXECUTE entries |

All 46 application routines have the PostgreSQL default PUBLIC EXECUTE ACL. The 46 comprise 33 trigger functions and 13 non-trigger routines. No explicit non-owner ACL entries were found for application relations or sequences. No SECURITY DEFINER routines were found.

## Security interpretation

- PUBLIC currently has no USAGE grant on the eight application schemas. Therefore, PUBLIC EXECUTE on a routine does not by itself make a schema-qualified application routine callable by an arbitrary role that lacks schema USAGE.
- A future least-privilege runtime role will need USAGE on the application schemas. Because PUBLIC EXECUTE is inherited by all roles, granting schema USAGE without first addressing the routine ACL would expose EXECUTE on all 46 routines to that runtime role.
- That includes dormant Sales & Dispatch and packing FG-transfer routines as well as stock approval/posting routines. It would defeat an intended narrow EXECUTE allowlist even if explicit GRANT statements name only a few routines.
- The PUBLIC EXECUTE entries are default PostgreSQL function ACLs, not evidence that PUBLIC can currently read or modify application tables. Table, sequence, and schema PUBLIC ACL checks returned zero rows.

## Required design controls — proposal only, not executed

Before granting application schema USAGE to a future runtime role:

1. Revoke EXECUTE on existing application routines from PUBLIC in all eight application schemas.
2. Add a GLOBAL owner-specific ALTER DEFAULT PRIVILEGES rule (without IN SCHEMA) so future functions created by the migration/object-owner identity do not receive PUBLIC EXECUTE by default. PostgreSQL documents that per-schema REVOKE cannot remove a privilege granted by the global default.
3. Explicitly grant EXECUTE only on the non-trigger routines proven necessary for reachable application routes. Current route evidence identifies core.get_next_document_no, inventory.approve_stock_document, and inventory.post_stock_document for purchase receipt/return workflows; even these remain subject to restored-database tests.
4. Do not grant direct EXECUTE on trigger functions to the runtime role merely because they are attached to tables. Existing triggers were created by the owner identity. Confirm trigger firing after PUBLIC EXECUTE revocation on a restored test database before staged migration.
5. Keep all trigger creation/alteration rights with the migration identity. The runtime role must not receive schema CREATE or TRIGGER rights.
6. Re-run ACL checks after the staged migration and prove that the runtime role can execute only the approved routines, while dormant Sales/Dispatch and packing transfer functions are denied.

## PostgreSQL behavior to validate in staging

The design relies on separating schema USAGE, routine EXECUTE, and trigger invocation. PostgreSQL documents that the role creating a trigger must have EXECUTE on its trigger function, and that a trigger runs as the role that queued the event unless the function is SECURITY DEFINER. Do not assume that the catalog ACL alone proves the exact EXECUTE requirement for DML against an existing trigger: demonstrate trigger firing after PUBLIC EXECUTE is revoked on a restored copy using the target PostgreSQL version before changing live ACLs.

Official PostgreSQL 18 references:
- https://www.postgresql.org/docs/current/ddl-priv.html (built-in PUBLIC EXECUTE default for functions/procedures)
- https://www.postgresql.org/docs/current/sql-alterdefaultprivileges.html (global defaults and per-schema REVOKE limitation)
- https://www.postgresql.org/docs/current/sql-createtrigger.html (EXECUTE required to create a trigger)
- https://www.postgresql.org/docs/current/trigger-definition.html (trigger execution role)

## Status

- PUBLIC ACL catalog inspection: complete, read-only.
- Existing PUBLIC EXECUTE: 46 routines.
- PUBLIC schema/table/sequence grants: none found in the eight application schemas.
- Live revokes, default-privilege changes, and runtime-role creation: not performed.
