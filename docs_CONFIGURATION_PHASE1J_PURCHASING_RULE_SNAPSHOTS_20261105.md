# Configuration Phase 1J — Purchasing Product and Unit Rule Snapshots

**Date:** 05-Nov-2026  
**Status:** Implemented and verified in SAFE WORKING COPY; full Goods Receipt workflow end-to-end remains blocked by the absence of an active supplier master record.

## Scope
Goods Receipt DRAFT creation now resolves and attaches two configuration identities for every receipt line:
1. `PRODUCT_DEFINITION` keyed by the actual item code.
2. `UNIT_DEFINITION` keyed by the selected unit code.

The resolver selects only one APPROVED version for the same company, exact type/key and receipt date. The selected version row is locked `FOR SHARE` and its exact payload/version ID is pinned. Multiple effective versions, wrong keys, invalid payloads, inactive product definitions or unsupported unit conversions fail closed.

When no approved version exists, the receipt line pins a clearly identified `SYSTEM_DEFAULT_MASTER` snapshot of the active existing master item/unit identity. This is not misrepresented as an approved configuration version.

## Unit-conversion boundary
This phase does **not** apply unit conversions or change received quantity, unit price, GST, freight, costing or PO matching. The existing Purchasing rule still requires the variant's exact default unit. If an approved Unit Definition would require a conversion (factor other than 1 or a different base unit), the receipt is blocked until a separately designed conversion workflow is implemented and tested. No silent multiplication/division is allowed.

## Database protection
Migration `20261105_008_purchasing_configuration_snapshots.sql` adds `purchasing.purchase_configuration_snapshots`.
- One immutable Product Definition and Unit Definition snapshot per receipt line/key.
- Snapshot parent receipt and line must belong to the same company.
- Parent must remain DRAFT.
- Creator and effective date must match the parent receipt.
- APPROVED_VERSION must point to a same-company, exact-type/key, approved and effective version with identical JSON payload.
- SYSTEM_DEFAULT_MASTER must identify the actual active master item or unit and its current code/name/precision.
- UPDATE and DELETE are rejected by a database trigger.

## Audit
Goods Receipt creation audit payload now records each line's configuration type/key, source, version ID and payload alongside the receipt's other audit details. Snapshot inserts, receipt/lines and audit row are in the same database transaction.

## Verification
- Configuration runtime suite: **16/16 passed**.
- Purchasing service suite: **7/7 passed**.
- Full application suite: **206/206 passed**.
- Python compilation passed.
- Application restarted; health returned `{"app":"ok","database":true}`.
- OpenAPI confirms existing Goods Receipt create/approve/post routes remain registered.
- Live resolver selected `SYSTEM_DEFAULT_MASTER` for NALKI and PCS; no rows were written.
- Transactional database probe created a temporary DRAFT receipt/line and two master snapshots, verified both inserts, verified UPDATE and DELETE rejection, then rolled the entire transaction back. Post-rollback snapshot count remained **0**.
- Read-only baseline: purchase receipts=0, receipt lines=0, purchase configuration snapshots=0, configuration versions=0, active company suppliers=0.
- Because there are currently no active supplier master records for company 1, the real Goods Receipt service could not be exercised end-to-end without inventing or inserting a supplier. No supplier was created.
- No purchase receipt, PO, stock, ledger, accounting, master data, configuration version, role or permission was changed.

## Backups
- Code snapshot: `BACKUP_PURCHASING_CONFIG_PINNING_20261105_225241`
- Database backup: `database/backups/ali_raza_erp_pre_purchasing_config_snapshot_20261105.dump`
- Migration: `database/migrations/20261105_008_purchasing_configuration_snapshots.sql`

## Remaining Purchasing integration
- Unit Conversion rules require a dedicated explicit quantity-conversion design, precision/rounding policy, PO unit compatibility, and line-level original/base quantity snapshots. Not enabled in this phase.
- Ownership Policy rules require product-family mapping and maker-checker controls. Supplier GRN remains OWN-only; PARTY material is not enabled here.
- Product Definition snapshots are validation/history only; they do not create or mutate master items.
- GST/tax rules, costing and accounting posting remain separate work; this phase does not infer a tax rate or post any financial/stock document.

**Completion boundary:** New Goods Receipt DRAFT lines now pin Product and Unit configuration identity/version evidence in the same transaction. End-to-end GRN workflow verification is pending an active supplier master record; no real purchasing record was created.