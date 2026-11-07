# Configuration Phase 1K — Approved Unit Conversion Engine

**Date:** 05-Nov-2026  
**Status:** Directional conversion resolver and Decimal calculation engine implemented and tested. NOT enabled in Purchasing or stock posting.

## Delivery
New module: `app/unit_conversion_service.py`.

- Canonical directional key: `{FROM}-TO-{TO}`, e.g. `KG-TO-G` or `BOX-TO-PCS`.
- Resolves exactly one same-company `UNIT_CONVERSION` version in APPROVED status, effective on the requested transaction date.
- Locks the approved configuration version with `FOR SHARE`.
- Validates the typed `UnitConversion` payload, active flag, exact source/target direction, configuration key and matching effective-from date.
- Verifies both source and target units exist and are active in `master.units`.
- Does not infer or reverse a conversion. A reverse direction requires its own separately approved rule.
- Returns the exact configuration version ID, factor, source/target codes, effective date and explicit rounding policy as immutable snapshot data.

## Arithmetic
`convert_unit_quantity()` uses Python Decimal arithmetic only:
- target quantity = source quantity × approved factor.
- rounding is explicit `ROUND_HALF_UP`.
- conversion rule precision must fit the target stock quantity scale (maximum 3 decimal places for this service boundary).
- negative, zero, NaN, infinite, invalid-factor and zero-after-rounding results are blocked.
- returns original quantity, source unit, factor, unrounded target, rounded target, target unit and rounding difference for audit/traceability.

## Important operational boundary
This engine is deliberately NOT wired into Goods Receipt, Purchase Orders, inventory stock documents or accounting. Current GRN line schema stores one quantity and one unit; stock ledger also stores one quantity and has scale 3. Before activating conversion, a separate schema and workflow phase must preserve:
1. entered/source quantity and source unit;
2. exact approved conversion version and factor;
3. unrounded target quantity and rounded base quantity;
4. target/base unit;
5. unit-price conversion (inverse relationship) and amount invariance;
6. PO ordered/received quantities in the PO's own unit, including partial receipts;
7. inventory posting only in the agreed stock/base unit;
8. supplier returns and reversal using original source/base snapshots.

No live quantity or unit behaviour was changed.

## Verification
- New unit-conversion tests: **16/16 passed**.
- Full application unit suite: **222/222 passed**.
- Python compilation passed.
- ERP health: `{"app":"ok","database":true}`.
- Active units confirmed in live DB: BOX, CONE, G, KG, L, M, PCS, SET.
- Approved UNIT_CONVERSION versions currently: **0**.
- Live resolver correctly failed closed for BOX-TO-PCS because no approved version exists.
- Existing purchase configuration snapshots: **0**.
- No configuration versions, purchase receipts, PO quantities, stock, ledger, accounting, master data, roles or permissions were changed.
- Code backup: `BACKUP_UNIT_CONVERSION_ENGINE_20261105_225954`.

## Next safe phase
Design and implement source/base quantity traceability for Goods Receipt and PO matching, including price normalization, stock posting, returns and reversal, with a dedicated migration and transactional tests. Do not enable alternate units until all paths pass.


## Purchasing and Inventory Traceability Discovery (next implementation gate)
Read-only inspection of live schema, routes and database functions found:
- Current database contains 0 purchase orders, 0 PO lines, 0 GRNs, 0 GRN lines, 0 purchase returns and 0 purchase-return lines. Active supplier count was already verified as 0 in Phase 1J.
- The Purchasing UI exposes PO information as a read-only listing; there is no PO create/edit/approve route in `app/main.py`. A complete PO workflow must be built before alternate-unit PO quantities can be tested.
- GRN approval creates one linked inward stock document. Its line quantity is copied from `purchase_receipt_lines.received_quantity`; GRN posting later updates PO `received_quantity` from the same GRN quantity.
- The generic inventory stock document and stock ledger have no unit_id column. `inventory.post_stock_document` moves the supplied numeric quantity into `inventory.stock_balances` and `inventory.stock_ledger`; both use numeric(18,3) quantity. Therefore inventory quantity must remain in the item's canonical base unit.
- Purchase Returns use the original GRN line's quantity/unit and later create outward stock document lines. Any conversion feature must preserve the original GRN conversion snapshot and convert the returned source quantity using that same factor/version; it must not resolve a newer rule at return time.
- GRN landed-cost calculation is based on entered quantity × entered unit price, then discounts/freight/other charges are allocated by net line value. Conversion must preserve line value exactly and normalize per-base-unit cost as source unit price ÷ source-to-base factor; rounding unit cost must not alter the line's six-decimal landed total.
- PO remaining-quantity enforcement currently compares GRN quantity directly with PO ordered/received quantity. Once alternate units are enabled, both sides must be compared in base quantity while retaining the original PO/source quantity and unit for display and audit.

### Required order of implementation
1. Build a real PO DRAFT → approval workflow with source quantity/unit, base quantity/unit and immutable approved conversion snapshot.
2. Add additive GRN source/base quantity fields and pin the conversion version used on the receipt date; preserve exact line value and normalize unit price.
3. Update PO matching/posting to compare base quantities and update base received quantity atomically.
4. Update supplier returns to reuse the original GRN conversion snapshot and create outward stock quantities in base units.
5. Verify reversal/rollback, partial receipts, partial returns, rounding boundaries and total-cost invariance in transactional tests.
6. Only then enable alternate units in the GRN UI. Until that full chain passes, current exact-default-unit behaviour remains enforced.

This discovery did not change schema, routes, database records, stock or accounting.