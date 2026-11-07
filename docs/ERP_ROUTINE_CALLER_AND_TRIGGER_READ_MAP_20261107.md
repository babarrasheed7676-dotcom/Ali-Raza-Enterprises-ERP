# ERP Routine Caller and Trigger Read Map — 7 November 2026

## Scope and safety

Read-only review of the 46 PostgreSQL routine definitions and static search of Python source in the Git mirror. No application code, database objects, roles, grants, ownership, DSN, or server state was changed.

## Trigger function behavior

- 44 non-internal triggers invoke 33 distinct trigger functions.
- All 33 trigger functions are SECURITY INVOKER and owned by postgres.
- Static inspection of all 33 function definitions found no SQL `INSERT INTO`, `UPDATE table`, or `DELETE FROM` statements. The functions act as validation/guard logic and return trigger records; they do not appear to perform cross-table DML.
- Their SQL SELECTs read parent/sibling records and cross-schema configuration/master/inventory/production data. Therefore, a runtime role that causes these triggers to execute needs the SELECT rights required by those guard queries, as well as the normal write rights on the triggering table.
- The static scan is not a formal PL/pgSQL parser. Dynamic SQL, unqualified references, nested calls, or unusual syntax still need review before a final grant set is approved.
- The migration identity, not the runtime identity, should own triggers and retain CREATE TRIGGER rights. Do not grant TRIGGER or schema CREATE to the web runtime role.

## Direct Python caller findings for non-trigger routines

Static search of all Python files under `app/` found three actual SQL call sites (the report-service occurrence of `inventory.post_stock_document` is explanatory text, not an execution):

| Routine | Direct caller | Observed operation / lifecycle |
|---|---|---|
| `core.get_next_document_no` | `app/purchasing_service.py` | Called while creating a purchase receipt number; routine updates `core.document_sequences`. |
| `inventory.approve_stock_document` | `app/purchasing_service.py` | Called in purchase receipt approval and purchase return approval paths. Routine validates document/user/transaction/lines and updates stock-document status to APPROVED. |
| `inventory.post_stock_document` | `app/purchasing_service.py` | Called in purchase receipt posting and purchase return posting paths. Routine updates stock balances, stock ledger, stock-document lines and stock-document status. Purchase return caller then updates the return status. |

These are the only three routine names found as direct Python references among the 13 non-trigger routines. This does not prove the other ten are unused: they may be invoked by database routines, dynamic SQL, external scripts, or future code. Do not grant EXECUTE on them without proving a live caller and testing its path.

## Routine exposure classification

| Routine group | Direct Python caller found? | Grant stance |
|---|---|---|
| Document number generation | Yes | Candidate EXECUTE only for the purchase receipt path; validate purchase return numbering separately if applicable. |
| Stock approval | Yes | Candidate EXECUTE for receipt/return approval paths only, after restored-DB role testing. |
| Stock posting | Yes | High-impact candidate EXECUTE for receipt/return posting paths only; keep explicit approval and posting separation. |
| Stock reservation/availability routines | No direct Python call found | Do not grant yet; trace possible DB callers and sales workflow. |
| Packing cost/FG transfer routines | No direct Python call found | Do not grant yet; trace packing workflow and database callers. |
| Sales lifecycle/reservation routines | No direct Python call found | Do not grant yet; trace sales routes and dispatch workflow. |

## Important details for least-privilege design

1. A routine's EXECUTE privilege is separate from the table/sequence privileges its SECURITY INVOKER body needs. For the three directly called routines, both layers must be mapped.
2. `inventory.post_stock_document` is particularly sensitive: it performs inventory balance and ledger writes. The runtime role must not receive broad direct write privileges on ledger/balance tables merely because a posting routine exists; test whether the routine can be safely called with narrowly scoped table grants, or consider a separately reviewed privileged execution boundary.
3. Because these routines are SECURITY INVOKER, they do not elevate the caller to the postgres owner. The current superuser connection masks the real table/sequence requirements.
4. The trigger guard functions also run with invoker rights; their SELECT dependencies must be included in the table grant matrix. No trigger function was observed to perform direct DML, but their read dependencies are still part of the effective permission surface.
5. The three serial/default sequence cases are `configuration.config_approval_events`, `configuration.config_audit_events`, and `configuration.config_versions`. The other 125 sequences are identity-owned. Verify actual insert behavior under a test runtime role before applying sequence grants.

## Next steps

- Resolve database-to-database routine calls, particularly whether any of the ten routines without Python callers are called by another routine.
- Trace all purchase receipt and return route call paths and transaction boundaries.
- Validate least-privilege behavior on a restored database copy, including DRAFT/APPROVED/POSTED lifecycle checks, rollback on failure, and sequence generation.
- Keep live role, password, DSN, grants, ownership, schema and production data unchanged until a separately approved migration plan exists.

## Status

Caller scan and trigger function static review complete as an intermediate design input. No final grants or role SQL are approved or applied.
