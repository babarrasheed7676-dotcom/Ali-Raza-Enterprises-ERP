# ERP Routine Caller and Trigger Read Map — 7 November 2026

## Scope and safety

Read-only review of the 46 PostgreSQL routine definitions, routine-to-routine references, and static search of Python source in the Git mirror. No application code, database objects, roles, grants, ownership, DSN, or server state was changed.

## Trigger function behavior

- 44 non-internal triggers invoke 33 distinct trigger functions.
- All 33 trigger functions are SECURITY INVOKER and owned by postgres.
- Static inspection of all 33 function definitions found no SQL INSERT INTO, UPDATE table, or DELETE FROM statements. The functions act as validation/guard logic and return trigger records; they do not appear to perform cross-table DML.
- Their SQL SELECTs read parent/sibling records and cross-schema configuration/master/inventory/production data. Therefore, a runtime role that causes these triggers to execute needs the SELECT rights required by those guard queries, as well as the normal write rights on the triggering table.
- The static scan is not a formal PL/pgSQL parser. Dynamic SQL, unqualified references, nested calls, or unusual syntax still need review before a final grant set is approved.
- The migration identity, not the runtime identity, should own triggers and retain CREATE TRIGGER rights. Do not grant TRIGGER or schema CREATE to the web runtime role.

## Direct Python caller findings for non-trigger routines

Static search of all Python files under app/ found three actual SQL call sites (the report-service occurrence of inventory.post_stock_document is explanatory text, not an execution):

| Routine | Direct caller | Observed operation / lifecycle |
|---|---|---|
| core.get_next_document_no | app/purchasing_service.py | Called while creating a purchase receipt number; routine updates core.document_sequences. |
| inventory.approve_stock_document | app/purchasing_service.py | Called in purchase receipt approval and purchase return approval paths. Routine validates document/user/transaction/lines and updates stock-document status to APPROVED. |
| inventory.post_stock_document | app/purchasing_service.py | Called in purchase receipt posting and purchase return posting paths. Routine updates stock balances, stock ledger, stock-document lines and stock-document status. Purchase return caller then updates the return status. |

These are the only three non-trigger routine names found as direct Python SQL references. This is not the full caller graph; the database routines themselves contain additional calls.

## Database routine-to-routine call graph

A static scan of all 46 retrieved routine definitions found these three cross-routine call edges:

| Caller routine | Calls |
|---|---|
| production.post_packing_fg_transfer | core.get_next_document_no; inventory.approve_stock_document; inventory.post_stock_document |
| sales.post_dispatch | inventory.approve_stock_document; inventory.consume_stock_reservation; inventory.post_stock_document |
| sales.reserve_sales_order_line | core.get_next_document_no |

Consequences:
- inventory.consume_stock_reservation has no direct Python call found, but is called by sales.post_dispatch.
- production.post_packing_fg_transfer and sales.post_dispatch have no direct Python SQL caller found in the current static scan, but they are database-level callers of high-impact stock routines.
- sales.reserve_sales_order_line has no direct Python caller found; it calls document numbering.
- Do not classify routines as unused based only on Python call-site search. Conversely, do not grant EXECUTE on a routine just because another dormant routine references it. First prove the caller route is reachable and part of the intended workflow.

## Routine exposure classification

| Routine group | Caller evidence | Grant stance |
|---|---|---|
| Document number generation | Direct purchase receipt Python call; indirect packing transfer and sales reservation calls | Candidate EXECUTE only for verified live workflows. |
| Stock approval | Direct purchase receipt/return calls; indirect packing transfer/dispatch calls | Candidate EXECUTE only for verified live workflows. |
| Stock posting | Direct purchase receipt/return calls; indirect packing transfer/dispatch calls | High-impact candidate EXECUTE; preserve separate approval/posting lifecycle and test on restored DB. |
| Stock reservation consumption | Called by sales.post_dispatch | No grant until sales dispatch caller route is proven live. |
| Stock availability | No direct Python or routine call found by this scan | Do not grant yet; inspect dynamic SQL and any external callers. |
| Packing cost / FG transfer | FG transfer routine calls stock functions; no Python caller found | Trace packing route reachability before grant. |
| Sales order/dispatch/reservation routines | Some internal routine-to-routine calls; no direct Python caller found | Trace sales routes and dispatch workflow before grant. |

## Important details for least-privilege design

1. A routine's EXECUTE privilege is separate from the table/sequence privileges its SECURITY INVOKER body needs. For directly called routines, both layers must be mapped.
2. inventory.post_stock_document is particularly sensitive: it performs inventory balance and ledger writes. The runtime role must not receive broad direct write privileges on ledger/balance tables merely because a posting routine exists; test whether the routine can be safely called with narrowly scoped table grants, or consider a separately reviewed privileged execution boundary.
3. Because these routines are SECURITY INVOKER, they do not elevate the caller to the postgres owner. The current superuser connection masks the real table/sequence requirements.
4. The trigger guard functions also run with invoker rights; their SELECT dependencies must be included in the table grant matrix. No trigger function was observed to perform direct DML, but their read dependencies are still part of the effective permission surface.
5. The three serial/default sequence cases are configuration.config_approval_events, configuration.config_audit_events, and configuration.config_versions. The other 125 sequences are identity-owned. Verify actual insert behavior under a test runtime role before applying sequence grants.

## Next steps

- Prove route reachability and transaction boundaries for packing transfer, sales dispatch, sales reservation, and all purchase receipt/return lifecycle paths.
- Resolve dynamic SQL, unqualified references, and any external script/migration callers.
- Build a verified table-operation matrix from direct Python SQL plus trigger-function SQL plus non-trigger routine SQL. Separate SELECT, INSERT, UPDATE, DELETE, sequence nextval, and routine EXECUTE.
- Validate least-privilege behavior on a restored database copy, including DRAFT/APPROVED/POSTED lifecycle checks, rollback on failure, and sequence generation.
- Keep live role, password, DSN, grants, ownership, schema and production data unchanged until a separately approved migration plan exists.

## Status

Trigger behavior and static routine call graph inspected read-only. The caller graph is an intermediate design input, not a final route-reachability proof. No final grants or role SQL are approved or applied.
