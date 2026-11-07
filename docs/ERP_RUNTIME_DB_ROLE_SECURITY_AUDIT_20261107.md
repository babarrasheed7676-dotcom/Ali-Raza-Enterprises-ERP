# ERP Runtime Database Role Security Audit — 7 November 2026

## Scope

Read-only inspection of the live database connection configured for the ERP application. No roles, passwords, DSNs, grants, ownership, schema objects, data, or application files were changed by the audit.

## Verified live findings

The application's configured DSN connects with:

- `current_user = postgres`
- `session_user = postgres`

The connected role has all of these PostgreSQL role attributes enabled:

| Attribute | Live value |
|---|---:|
| SUPERUSER | true |
| CREATEROLE | true |
| CREATEDB | true |
| REPLICATION | true |
| BYPASSRLS | true |
| INHERIT | true |
| LOGIN | true |

No explicit role memberships were returned for the connected role. This does not reduce its superuser authority.

The eight application schemas are owned by `postgres` and the current role has CREATE and USAGE on each:

| Schema | Objects listed in role table grants | TRIGGER grant rows | TRUNCATE grant rows |
|---|---:|---:|---:|
| accounting | 21 | 3 | 3 |
| configuration | 21 | 3 | 3 |
| core | 91 | 13 | 13 |
| inventory | 84 | 12 | 12 |
| master | 98 | 14 | 14 |
| production | 469 | 67 | 67 |
| purchasing | 98 | 14 | 14 |
| sales | 28 | 4 | 4 |

These are counts of privilege rows returned by `information_schema.role_table_grants`, not unique object counts. A superuser can bypass ordinary table ACL checks regardless.

The three Baby Cone tables (`production.baby_cone_orders`, `production.baby_cone_cost_lines`, and `production.baby_cone_loss_lines`) are owned by `postgres`; the connected role has TRIGGER and TRUNCATE privileges on them.

## Security impact

This is a critical least-privilege gap for a multi-user factory ERP. A web application process using a PostgreSQL superuser can bypass row/table privileges, alter schema objects, disable triggers, access all company data, and perform destructive operations beyond the intended module permission model. Application permissions and CSRF checks remain important, but they cannot contain a full database-superuser compromise.

In particular, the proposed Baby Cone DRAFT guard triggers are not sufficient enforcement while the application connects as the owning superuser. The app can disable or alter them. The proposal must remain unapplied until a least-privilege runtime role is designed and tested.

## Recommended controlled remediation — design only

1. Inventory every SQL query, table, sequence, function, view, report, background task, assistant path, and migration path used by the app.
2. Separate runtime and migration identities. Runtime identity must not be SUPERUSER, CREATEROLE, CREATEDB, REPLICATION, BYPASSRLS, object owner, or able to CREATE in application schemas; it must not have TRIGGER, TRUNCATE, ALTER, DROP, or broad DDL privileges.
3. Grant only the exact SELECT/INSERT/UPDATE/DELETE/USAGE/EXECUTE rights needed by application paths. Do not assume all 8 schemas need all CRUD privileges.
4. Keep migrations on a separately controlled owner/admin path; never use the runtime credential for DDL.
5. Test the full application against a restored database copy using the candidate runtime role. Include login, dashboard, purchasing, production, inventory, accounting, reports, assistant, audit logging, sequence usage, and transaction rollback.
6. Verify denied operations explicitly: CREATE/ALTER/DROP, TRUNCATE, trigger disable, cross-company access, and writes outside the intended module.
7. Stage a DSN switch with a verified backup and preserved rollback DSN; perform a health and module smoke check before deployment.
8. Rotate credentials only through the approved secret-management workflow. Never place plaintext passwords in source code, logs, Git, or documentation.
9. Do not change the live role, password, DSN, grants, ownership, or schema as part of this read-only audit. These require a separately scoped explicit approval and rollback plan.

## Status

- Audit: complete, read-only.
- Live database: unchanged.
- Runtime DSN: unchanged.
- Baby Cone guard proposal: documentation only, not executed.
- Immediate priority before relying on DB-level lifecycle guards: least-privilege runtime-role design and staged validation.
