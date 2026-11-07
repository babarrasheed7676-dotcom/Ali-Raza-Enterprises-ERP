# Configuration Phase 1I — Controlled Item Variant Creation

**Date:** 05-Nov-2026  
**Status:** Implemented and verified in SAFE WORKING COPY.

## Delivery
The Configuration master editor now supports creating new `master.item_variants` through the existing CSRF-protected POST API, in addition to the prior limited edit capability.

## Required and optional fields
- Required: active `item_id`, unique-per-item `variant_code`, and active `default_unit_id` (defaults to the item's base unit).
- Default unit must exactly match the item's base unit. Any unit conversion must be separately configured; this editor cannot silently redefine quantity semantics.
- Optional: display name, brand, shade, yarn count and fiber type.
- A selected shade must be active. Its brand is authoritative; a separately supplied brand must match it.
- Nalki and Label variants require an active brand and a shade belonging to that brand.
- Yarn, Big Cone and Baby Cone variants require both an active yarn count and active fiber type.
- Other item types accept only validated optional attributes; no unverified assumptions are made about shade tracking.
- The item itself must be active. No item, unit, brand, shade, yarn-count or fiber-type identity can be supplied as free text in place of a validated active master ID.

## Audit and transaction
- Variant insert and `core.audit_log` entry are performed in the same database transaction.
- No hard delete.
- Existing variant identity fields remain immutable on edit; only display name and active status can be edited.
- Deactivation of a variant with non-zero stock remains blocked.
- The UI displays active item IDs/base units, yarn-count IDs and fiber-type IDs to support validated JSON entry.

## Verification
- Configuration master-data tests: **12/12 passed**.
- Full application suite: **201/201 passed**.
- Python compilation passed.
- Jinja template rendered in editor-enabled and view-only modes.
- Inline JavaScript syntax passed Node check.
- Application restarted; health: `{"app":"ok","database":true}`.
- OpenAPI confirms POST create and PUT update routes.
- A real service-level create was executed inside an outer rollback transaction using a temporary FUEL_WOOD variant code. Both the variant and its audit row were confirmed absent after rollback.
- A Nalki variant without shade was rejected before insert.
- Live read-only counts after verification: item variants 5,423; Configuration audit rows 0; Configuration versions 0; Packing configuration snapshots 0.
- No actual item variant, brand, shade, unit, configuration version, packing order, stock, ledger, labour, FG transfer, accounting entry, role or permission was changed.

## Backup
`BACKUP_CONFIGURATION_VARIANT_CREATE_20261105_224531`

## Remaining boundaries
- Editor continues to use validated JSON rather than a fully guided field-by-field variant wizard.
- No actual master record was created during implementation.
- Configuration rules still need separate operational adapters/snapshots for Purchasing, Production, Outside Labeling and costing. Nalki Packing is the first integrated consumer.
- No factory deployment or operational posting.

**Completion boundary:** Brand, Unit, Shade and Item Variant master-data create/edit paths are now available within the validated scope. Existing production identities remain unchanged.
