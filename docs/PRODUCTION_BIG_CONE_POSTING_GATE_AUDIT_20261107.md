# Big Cone Approval and Posting Gate Audit

**Date:** 2026-11-07  
**Scope:** Read-only application, database schema, trigger, and inventory-engine audit.  
**Safety:** No database writes, schema changes, stock movements, production records, or server restarts were performed.

## Verified current state

- Big Cone currently exposes only the DRAFT create page and DRAFT save route in `app/main.py`; no Big Cone approve, post, cancel, or reverse route is present.
- `app/big_cone_draft_service.py` explicitly saves the header and material/output lineage as DRAFT. It does not reserve or move inventory.
- Source rows are restricted to a same-company POSTED Dyeing order's `DYED_THREAD` output, at the single active `RAW_STORE` location and `DYEING` process stage.
- Source rows are locked while allocations are checked. The database trigger serializes source allocation and caps combined non-cancelled/non-reversed Big Cone allocations to the source Dyeing output quantity.
- Output rows reference their exact material input line. Database guards preserve item, batch, ownership, owner, unit, physical godown, and active `BIG_CONE` process-stage identity.
- OWN/PARTY ownership and owner-party identity are carried from the source. PARTY input is blocked at draft creation if its locked unit cost is absent.
- The database has active `STOCK_RECLASSIFICATION` and `STOCK_TRANSFER` transaction types. The canonical inventory engine supports paired transfer/reclassification movements and updates stock balances by location, ownership, owner, and process stage. The one physical godown can therefore remain unchanged while process stage changes.
- The canonical stock engine exposes `inventory.approve_stock_document` and `inventory.post_stock_document`; purchasing demonstrates transaction-scoped locking, document linking through inventory reference fields, and atomic use of those routines.
- The Big Cone header has `approved_by/approved_at` and `posted_by/posted_at`, but no dedicated stock-document ID column. Existing `inventory.stock_documents.reference_document_type/reference_document_id` fields are a possible durable link; this must be protected by uniqueness/idempotency checks before implementation.

## Posting blockers — do not bypass

1. **Unreconciled material difference:** Draft input and output quantities can differ. The arithmetic difference is deliberately not measured wastage. The current Big Cone schema has a non-null `wastage_quantity_kg` column with a zero default, but that value is only a database-required placeholder in DRAFT. There is no verified Big Cone return/reusable-material line in the current workflow. Posting must not silently discard the difference, call it wastage, or create an unbalanced stock movement. Require an actual measured reconciliation (wastage and/or verified return/reusable material) before stock posting.
2. **Process-cost allocation:** Header labour, electricity, and machine costs are captured, but output-line cost is currently calculated from the upstream source unit cost multiplied by output quantity. The captured Big Cone process costs are not allocated into output-line cost. Do not invent a costing allocation or post understated downstream cost; define and test the approved allocation basis first.
3. **Stock document lifecycle:** Approval and posting must be separate, permission-gated actions. Each must lock the Big Cone order and source/output lines, verify current stock by exact item/batch/OWN-or-PARTY owner/location/stage, create exactly one linked stock reclassification document, and call the canonical inventory routines inside the same database transaction. Posting must be idempotent and roll back all linked status changes if inventory posting fails.
4. **Destination semantics:** `BABY_CONE`, `NALKI`, `DIRECT_SALE`, and `OTHER` are process destinations, not separate godowns. The physical location must remain the single `RAW_STORE`; process-stage transitions and destination eligibility must be validated independently.

## Safe implementation sequence

1. Add a read-only Big Cone approval-readiness/preflight view that reports source availability, exact ownership and locked-rate checks, process cost completeness, and unreconciled quantity.
2. Define the business-approved reconciliation and Big Cone process-cost allocation rules; do not assume either.
3. Implement approval as a DRAFT-to-APPROVED transition only, with `production.approve`, audit logging, source revalidation, and no stock movement.
4. Implement posting separately with `production.post`, one durable linked inventory reclassification, paired DYEING-stage OUT / BIG_CONE-stage IN lines at the same physical godown, canonical inventory approval/post routines, and one atomic transaction.
5. Add regression tests for duplicate approval/post, insufficient stock, concurrent source allocation, cross-company/source mismatch, OWN/PARTY preservation, exact single-godown stage transfer, failed inventory rollback, and audit trail.
6. Keep cancel/reverse as separate controlled workflows; never edit posted ledger rows.

## Current environment check

- ERP health endpoint: HTTP 200; app `ok`; database `true`.
- GitHub mirror: branch `main`, clean and synchronized with `origin/main` at `15daa2620d0092b88b8f1f0a86d27b835d403b67` at audit time.

**Conclusion:** Big Cone DRAFT lineage and source-allocation safeguards are in place. Approval/posting is intentionally not implemented yet because material reconciliation and process-cost allocation are unresolved accounting controls. The safe next step is a read-only readiness/preflight feature, followed by approval/posting only after those controls are defined.


## Read-only readiness preflight added

- Added `GET /modules/production/big-cone/{big_cone_order_id}/readiness`, protected by `production.view`.
- Successful Big Cone DRAFT save now opens its read-only readiness report; it still performs no approval, reservation, posting, or stock movement.
- The report shows document state, input/output totals, unreconciled difference (never measured wastage), process costs, exact input/output lineage, and current source stock.
- Current source stock is checked using the exact stock-balance dimensions: company, item variant, batch, single physical location, ownership, owner party, and DYEING process stage.
- The preflight aggregates all same-dimension lines and includes other active DRAFT/APPROVED Big Cone claims once, preventing two individually-small lines/drafts from each appearing affordable against the same balance.
- PARTY locked-rate presence is rechecked. The screen always reports not-ready until reconciliation and process-cost allocation controls are approved and implemented.
- All readiness SELECT statements were validated with PostgreSQL EXPLAIN inside a read-only transaction; no records were created or changed.
- Validation: Python compilation PASS; Jinja template compilation PASS; OpenAPI route registration PASS; full suite **380 tests PASS**.
- Deployment note: changes are on disk and GitHub. The currently running Uvicorn process was intentionally not restarted, so the new route becomes live only after an authorized controlled restart.
