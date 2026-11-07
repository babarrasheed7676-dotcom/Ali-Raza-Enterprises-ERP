# ERP Least-Privilege Runtime Role — Staged Migration Proposal (DESIGN ONLY)
Date: 8 November 2026

## Decision and safety boundary

This is a staging-only proposal, not an authorization to change the live database. The live application currently connects as the postgres superuser, which owns all eight application schemas and their objects. Do not run this against the live database. Do not create a runtime login, rotate a password, change DSN, change ownership, or apply grants/revokes until a restored copy has passed the validation gates below and a separate deployment approval is recorded.

No database, application, server, or credential changes were made while preparing this document.

## Evidence used

- Eight application schemas: accounting, configuration, core, inventory, master, production, purchasing, sales.
- 130 tables, 128 sequences, 44 triggers, 33 trigger functions, 13 non-trigger routines.
- 46 application routines currently have default PUBLIC EXECUTE.
- No PUBLIC grants were found on the eight application schemas, tables/views, or sequences.
- The web application currently connects as postgres (SUPERUSER, CREATEROLE, CREATEDB, REPLICATION, BYPASSRLS); all application objects are owned by postgres.
- Direct literal-SQL scan found 70 candidate tables across 41 Python files. It is not yet a complete table-operation matrix: unqualified/dynamic SQL, trigger indirect reads, and nested routines remain to be resolved.
- Current protected purchase approval/post routes call three non-trigger routines: core.get_next_document_no, inventory.approve_stock_document, inventory.post_stock_document. This is a candidate list only.
- Sales & Dispatch is Planned and no packing FG-transfer route was found. Do not grant their routines to the web runtime role.

## Target identity model

| Identity | Purpose | Required authority |
|---|---|---|
| are_erp_owner | Object/migration owner, controlled administrative use | Owns schemas/objects; DDL and migrations; never used by web app |
| are_erp_runtime | FastAPI web process | LOGIN only; no superuser, role/database creation, replication, bypass-RLS, object ownership, schema CREATE, TRIGGER, TRUNCATE, or DDL |
| are_erp_readonly (optional later) | Reporting/support | Only separately reviewed SELECT access; not needed for initial cutover |

Do not make the runtime role a member of the owner role. Keep owner credentials out of app configuration and runtime environment. Provision its password interactively through an approved secret workflow (for example, psql \\password); never place a literal password in SQL, source, logs, or Git.

## Critical PUBLIC EXECUTE control

A schema USAGE grant makes PUBLIC's default EXECUTE grants relevant. The 46 existing application routines must be handled before granting runtime schema USAGE.

PostgreSQL's global default privilege REVOKE cannot be undone by a per-schema REVOKE. The existing postgres-owned public schema has 212 routines with PUBLIC EXECUTE, so preserve that schema's existing default explicitly if changing postgres's global default.

### Staging-only SQL skeleton — review before use

Run only on a freshly restored, isolated database copy as the object-owner/admin identity. First capture a full backup and export current role, ACL, and default-ACL state.

\`\`\`sql
-- 0. Confirm you are on the restored staging database and as the expected owner.
SELECT current_database(), current_user, session_user;

-- 1. Create a non-superuser login WITHOUT embedding a password.
-- Use an approved interactive secret workflow to set its password afterwards.
CREATE ROLE are_erp_runtime
  LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOREPLICATION NOBYPASSRLS INHERIT;

-- 2. Prevent future functions created by postgres from inheriting PUBLIC EXECUTE.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- 3. Preserve the observed existing public-schema default behavior.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO PUBLIC;

-- 4. Remove PUBLIC EXECUTE from existing routines in the eight ERP schemas.
DO $acl$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT n.nspname, p.proname, pg_get_function_identity_arguments(p.oid) AS args,
           p.prokind
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname IN
      ('accounting','configuration','core','inventory',
       'master','production','purchasing','sales')
  LOOP
    EXECUTE format(
      'REVOKE EXECUTE ON ROUTINE %I.%I(%s) FROM PUBLIC',
      r.nspname, r.proname, r.args
    );
  END LOOP;
END
$acl$;

-- 5. Initial schema visibility only; exact object grants are deliberately omitted
-- until the table/sequence/trigger dependency matrix is complete.
GRANT USAGE ON SCHEMA
  accounting, configuration, core, inventory,
  master, production, purchasing, sales
TO are_erp_runtime;

-- 6. Candidate routine EXECUTE grants only; validate each on restored staging.
GRANT EXECUTE ON FUNCTION core.get_next_document_no(/* exact signature to confirm */)
TO are_erp_runtime;
\`\`\`

Important: the signature above is intentionally incomplete and is NOT executable as written. Resolve the exact routine identity arguments from the target database before use. The two inventory routine signatures must likewise be read from that restored database before any GRANT. Do not grant trigger-function EXECUTE to the runtime role merely because the functions are attached to triggers. Test ordinary DML with PUBLIC EXECUTE revoked; the target PostgreSQL version's actual behavior is a hard gate.

The routine-revoke DO block covers procedures/functions/aggregates in the eight named schemas by identity signature. Review it against the exact PostgreSQL 18 staging catalog first; do not use it as a blind production script.

## Exact object grants — intentionally blocked pending evidence

Do not use blanket grants such as ALL TABLES, ALL SEQUENCES, or ALL FUNCTIONS. The candidate direct-SQL matrix is incomplete and trigger functions are SECURITY INVOKER with cross-schema reads. For every table, finish a matrix with:
- SELECT / INSERT / UPDATE / DELETE individually;
- service/route caller and whether route is reachable;
- trigger-function reads and writes;
- nested routine reads/writes;
- sequence nextval/currval behavior (especially 3 explicit nextval defaults and 125 identity sequences);
- whether the object is unused, migration-only, or admin-only.

No DELETE or TRUNCATE grant should be included unless a concrete reachable workflow and a test prove it necessary. Never grant TRUNCATE, TRIGGER, REFERENCES, schema CREATE, ownership, or DDL to the runtime role as a convenience.

## Mandatory restored-database validation gates

1. Restore a current verified backup into an isolated PostgreSQL 18 staging instance; prove staging DB name and endpoint before every migration run.
2. Capture baseline schema/object counts, owners, role attributes, all ACLs, default ACLs, trigger definitions, sequence ownership, and key ERP invariants.
3. Apply the candidate role and PUBLIC routine ACL changes on staging only.
4. Add exact table and sequence grants incrementally from the completed matrix; do not proceed with incomplete/unqualified/dynamic SQL.
5. Run focused tests for authentication/session lifecycle, dashboard, assistant CSRF, configuration, purchasing receipt/return draft→approval→posting, production stages, inventory, accounting journals/reports, audit logging, sequence generation, and transaction rollback. Include negative tests for every denied operation.
6. Prove existing triggers fire successfully after PUBLIC EXECUTE revocation, including stock-document, journal, production lineage, ownership-use, packing and purchase snapshot guards.
7. Prove runtime cannot CREATE/ALTER/DROP objects, create roles/databases, disable triggers, TRUNCATE, access unapproved routines, bypass RLS, or write to unapproved tables.
8. Compare stock ledger/balances, posted-document counts, trial balance, inventory valuation, and all relevant control totals with the pre-test restored baseline.
9. Only after all gates pass, prepare a separate cutover plan: backup, owner credentials escrow, secret injection, DSN switch, health/module smoke tests, rollback DSN, and a defined maintenance window.

## Rollback outline — staging first

- Restore the pre-migration staging snapshot if any test fails; do not attempt ad-hoc partial repair.
- For ACL-only rollback, restore the captured exact routine ACLs and default-privilege state from the pre-change catalog export. Do not assume every routine originally had identical explicit ACLs without verifying the capture.
- Reapply the original DSN only as part of an approved deployment rollback; do not store plaintext credentials in this document.
- Verify schema/object owners, role attributes, trigger definitions, ACLs, sequences, and ERP control totals after rollback.

## Open blockers

- Full unqualified/dynamic SQL and route-to-object matrix not yet complete.
- Exact signatures of the three candidate non-trigger routines must be confirmed on restored staging.
- Trigger execution after PUBLIC EXECUTE revoke is unproven.
- Exact sequence privileges for identity and explicit nextval defaults are unproven.
- Runtime-role module smoke tests and negative privilege tests are not yet run.
- The 212 postgres-owned public-schema routine default behavior must remain unchanged.
- No live change is authorized by this design document.

## Current status

DESIGN ONLY — NOT EXECUTED. Live database, runtime role, grants, default privileges, ownership, DSN, app code, and server state remain unchanged.
