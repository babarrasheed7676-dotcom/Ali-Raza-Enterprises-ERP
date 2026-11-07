# ERP Trigger, Routine and Sequence Privilege Audit — 7 November 2026

## Scope and safety

Read-only PostgreSQL catalog inspection against the currently configured application connection, plus static inspection of retrieved routine definitions. No database writes, role/grant/ownership changes, DSN changes, app changes, or server restart were performed. Temporary inspection scripts and result files were removed from the safe working copy after analysis.

## Verified catalog inventory

| Object | Verified count | Finding |
|---|---:|---|
| Non-internal triggers | 44 | Installed across accounting, inventory, production and purchasing |
| Distinct trigger functions | 33 | All return trigger; all owned by postgres |
| Application routines total | 46 | 33 trigger functions + 13 non-trigger routines |
| Non-trigger routines | 13 | All owned by postgres; all SECURITY INVOKER (prosecdef=false) |
| Sequences | 128 | All owned by postgres and linked to a table column |
| Identity-owned sequences | 125 | Dependency type `i` |
| Serial/default-owned sequences | 3 | Dependency type `a`; explicit nextval defaults found on three configuration event/version tables |
| SECURITY DEFINER routines | 0 | None found in the eight application schemas |
| Default ACL entries | 0 | No pg_default_acl overrides found in the earlier catalog inventory |

### Trigger distribution

- accounting: 3
- inventory: 1
- production: 39
- purchasing: 1
- Total: 44

The triggers protect journal mutation and posted journal totals, stock-document mutation, production source lineage/immutability, Baby Cone/Big Cone/Dyeing source constraints, party ownership-use approval/cost snapshots, packing configuration/material/allocations, and purchasing configuration snapshots.

## Security implications for runtime-role design

1. All 33 trigger functions are SECURITY INVOKER. The trigger function owner does not provide an elevated privilege boundary for ordinary trigger execution. The invoking application role must have the underlying table privileges required by the trigger function's SQL, in addition to privileges on the table it directly modifies.
2. Do not grant EXECUTE on trigger functions to the runtime role merely because they are attached to tables. PostgreSQL documents that the role creating a trigger must have EXECUTE on its trigger function; the migration/owner identity must retain that ability and trigger-management rights. The exact DML-time EXECUTE behavior after PUBLIC revocation must be tested on a restored database before any live ACL change. The runtime role should not receive TRIGGER or schema CREATE rights.
3. The trigger functions include cross-schema reads. Examples include production guards consulting configuration.config_versions, master item/unit/ownership/process-stage records, inventory locations/batches/stock-document lines, core locations, and upstream/downstream production documents. A table-level grant matrix must account for these indirect reads.
4. Some trigger routines also inspect parent and sibling rows to enforce immutability and status gates. Required SELECT access is therefore broader than the direct SQL write paths alone, but should be granted only for the exact referenced tables and operations.
5. None of the inspected routines is SECURITY DEFINER. Do not introduce SECURITY DEFINER as a shortcut for this migration; that would require a separate hardened function-owner/search_path design and security review.

## Non-trigger routine inventory

There are 13 non-trigger routines:

- core.get_next_document_no
- inventory.approve_stock_document
- inventory.consume_stock_reservation
- inventory.get_available_stock
- inventory.post_stock_document
- production.calculate_packing_cost
- production.calculate_packing_cost_test
- production.post_packing_fg_transfer
- sales.cancel_sales_order
- sales.confirm_sales_order
- sales.get_sales_order_line_remaining
- sales.post_dispatch
- sales.reserve_sales_order_line

Static search of Python files found direct name references for only three routines: `core.get_next_document_no`, `inventory.approve_stock_document`, and `inventory.post_stock_document`. These references are in purchasing/accounting service code. The other routines may be dormant, called by other database routines, or invoked through dynamic/unqualified SQL not captured by this narrow search. Do not grant EXECUTE to every routine simply because it exists.

### Routine write-path observations

- `core.get_next_document_no` updates `core.document_sequences`.
- `inventory.approve_stock_document` updates `inventory.stock_documents` and validates users, transaction types and stock-document lines.
- `inventory.post_stock_document` updates stock balances/documents/lines and inserts stock ledger and balance rows. It has broad inventory consequences and must be separately approved and tested before runtime EXECUTE is enabled.
- Sales routines mutate sales documents and inventory reservation/stock-document structures. Their application invocation path must be confirmed before any grant is considered.
- Packing-cost and FG-transfer routines update production records and/or create inventory stock documents. Treat them as high-impact routines until the exact caller lifecycle is established.

## Sequence findings

All 128 sequences are owned by `postgres` and have an ownership dependency to a table column. 125 are identity sequences; three are serial/default sequences with explicit `nextval` defaults:

- configuration.config_approval_events.id
- configuration.config_audit_events.id
- configuration.config_versions.id

The three explicit nextval defaults require the runtime role to have the appropriate sequence privilege when inserting into their parent tables. Identity columns should be validated on a restored test database using the intended role; do not issue blanket USAGE/SELECT/UPDATE on all 128 sequences without that test. Sequence ownership must remain with the migration/owner role, not the application runtime role.

## Why the dependency query returned zero rows

PostgreSQL's `pg_depend` does not provide a complete table dependency graph for PL/pgSQL function bodies. The zero routine-to-table dependency rows are not evidence that the routines do not access tables. This audit therefore extracted `pg_get_functiondef` for all 46 routines and statically scanned the function text. The scan is useful for candidates but does not resolve dynamic SQL, unqualified references, record fields, nested function calls, or every indirect effect.

## Remaining work before a least-privilege grant matrix

1. Trace the actual callers and transaction lifecycle of all 13 non-trigger routines, including route reachability and dormant procedures.
2. Build a verified table-operation matrix from direct Python SQL plus trigger-function SQL plus non-trigger routine SQL. Separate SELECT, INSERT, UPDATE, DELETE, sequence nextval, and routine EXECUTE.
3. Resolve unqualified and dynamic SQL, including function-to-function calls, and inspect any external scripts/migrations.
4. Validate table-level grants and sequence behavior on a restored database copy with a non-owner, non-superuser role.
5. Test all application modules and failure cases; explicitly verify that runtime cannot CREATE, ALTER, DROP, TRUNCATE, CREATE TRIGGER, create roles/databases, bypass RLS, or own application objects.
6. Only then prepare a staged DSN migration and rollback plan. Live role, password, grants, ownership and DSN remain unchanged pending separate explicit approval.

## Status

- Trigger catalog and definitions: inspected read-only.
- Non-trigger routine definitions: inspected read-only.
- Sequence ownership/dependency: inspected read-only.
- Exact least-privilege table/sequence/routine grants: not yet approved or generated.
- Live database and application runtime: unchanged.
