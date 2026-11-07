# Configuration Phase 1G — Audited Master Data Editing

**Date:** 05-Nov-2026  
**Status:** Master-data create/edit foundation implemented in the SAFE WORKING COPY.

## Delivered
- Added `app/configuration_master_service.py` for controlled master-data operations.
- Added CSRF-protected POST and PUT endpoints:
  - `/configuration/api/master/{record_type}`
  - `/configuration/api/master/{record_type}/{record_id}`
- Endpoints require the existing `configuration.create` permission (ERP_ADMIN role only under the current permission catalog).
- Added a master-data editor to the Configuration page and Edit actions for records on the current paginated page.
- Every successful change writes a `core.audit_log` entry in the same database transaction.
- No hard delete operation exists.

## Supported scope
- **Brands:** create new brand; edit display name and description. Brand code is immutable after creation.
- **Units:** create new unit; edit display name. Unit code, unit type and decimal precision are immutable after creation to avoid silently changing historical quantity semantics.
- **Shades:** create shade for an existing active brand and optional active shade category; edit shade name, category, common flag and active flag. Brand and shade code are immutable.
- **Item variants:** edit display name and active flag only. Variant code, item, brand, shade and unit identity are immutable. New variants are intentionally blocked here until the dedicated item/variant setup workflow can validate the complete item definition.

## Dependency and safety guards
- No hard deletes.
- Brand deactivation is blocked while active shades, active variants or non-zero stock depend on it.
- Shade deactivation is blocked while active variants or non-zero stock depend on it.
- Unit deactivation is blocked while items, variants or machines reference it.
- Variant deactivation is blocked while its stock balance is non-zero.
- Master table identifiers, variant identity fields, stock ledger, inventory, posted documents and accounting records are not rewritten.
- Brands, Units and Shades are shared master tables in the current schema (not company-scoped). The endpoints therefore preserve shared identity and record all changes against the authenticated company/user in the audit log.
- View-only users do not see master-data edit controls. The API independently enforces `configuration.create`.

## Read-only live baseline
- Brands: 3
- Units: 8
- Shades: 2,709
- Item Variants: 5,423
- Page preview: 50 records per page for Shades and Item Variants.
- Master-data read queries returned successfully with no query error.
- Configuration-specific audit rows before any operator edits: 0.
- Configuration versions at verification: 0.

## Verification
- Full application suite: **184/184 tests passed**.
- Configuration-specific suite: 44/44 passed.
- Python compilation passed.
- Jinja template rendered for editor-enabled and view-only contexts.
- Inline JavaScript syntax passed Node `--check`.
- FastAPI route registry includes both POST and PUT master-data endpoints.
- Application restarted; health: `{"app":"ok","database":true}`.
- Final read-only baseline confirmed the four master record counts above and no configuration audit/version records created by this implementation.

## Not included / next gates
- No live master-data create/edit/deactivate operation was performed during implementation; no sample/dummy master record was inserted.
- No new item variant creation. This requires a dedicated item/variant workflow that validates item category, base unit, tracking flags, shade/brand relationships, ownership, and existing item code conventions.
- The current editor uses validated JSON payloads. A field-based form can replace this after the business-specific variant setup is designed.
- Approved configuration rule versions still need controlled, version-pinned adoption by Purchasing, Production, Nalki, Outside Labeling, Packing and costing.
- Global master-table governance and access separation should be reviewed before introducing a second company/tenant.

## Backup
`BACKUP_CONFIGURATION_PHASE1G_MASTER_DATA_20261105_223211`

**Completion boundary:** Existing master data can now be managed through audited, non-destructive operations within the explicitly supported scope. This phase does not claim that all master-data types or all operational rule integrations are complete.
