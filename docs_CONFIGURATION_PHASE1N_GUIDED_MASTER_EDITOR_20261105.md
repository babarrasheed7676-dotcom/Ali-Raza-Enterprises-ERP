# Configuration Phase 1N — Guided Master Editor
Date: 2026-11-05

## Scope
Replaced the master-data JSON-first input with guided fields for BRAND, UNIT, SHADE and VARIANT creation/edit. Existing audited POST/PUT API routes and service transaction boundaries are unchanged.

## UI behavior
- Brand: create code/name/description/active; edit name/description/active only.
- Unit: create code/name/type/decimal places/active; edit name/active only. Existing unit code/type/precision remain immutable.
- Shade: create using active Brand selection, shade code/name/common/active; edit shade name/common/active only. Existing shade brand/code/category identity remains unchanged.
- Variant: create by selecting active Item; base unit is loaded automatically from that item's actual base unit. The UI does not permit alternate unit selection.
- Nalki and Label items require Brand and a Shade filtered to that Brand.
- Yarn, Big Cone and Baby Cone items require active Yarn Count and Fiber Type.
- Variant edit remains limited to name and active status; item, variant code, unit, shade, brand and tracking dimensions are not editable.
- Advanced JSON is retained as a collapsed generated-payload review, not as the primary data-entry surface.
- All data still posts to existing CSRF-protected endpoints. Existing backend validation and transactional audit logging remain authoritative.

## Data loading
get_configuration_master_data() now also returns all active shades belonging to active brands as read-only dropdown options. Current verified option counts: 3 brands, 8 units, 10 active items, 4 active yarn counts, 7 active fiber types, 2,709 active shades. The normal paginated master tables are unchanged.

## Safety
- No master data was created or edited.
- No schema or migration.
- No inventory, stock, production, purchasing, accounting, roles or permissions changed.
- No change to the single-godown model or Nalki packaging/ownership rules.

## Backup
BACKUP_CONFIGURATION_GUIDED_EDITOR_20261105_231129

## Verification
- Full application suite: 222/222 passed.
- Python compileall: passed.
- Jinja template render: passed.
- Extracted template JavaScript node --check: passed.
- Live read-only master-data options query: no error; 2,709 shade options loaded.
- ERP health endpoint: app=ok, database=true.

## Remaining work
- Browser interaction smoke test for all four editor types, especially item → base unit, item type → required tracking fields, and brand → shade filtering.
- Consider server-side paginated/searchable dropdown API if master data grows materially beyond current counts.
- Configuration rule approval integration into further operational modules remains separate and gated.