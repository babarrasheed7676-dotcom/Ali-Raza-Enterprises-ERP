# Nalki Packing — Phase 2C: 100-Shade Assortment Draft UI and Service
Date: 05-Nov-2026
Backup: BACKUP_PACKING_PHASE2C_ASSORTMENT_UI_20261105_213019

## Confirmed business rules applied
1. One finished wall box contains 100 Nalki pieces: 100 different shades, one piece of each shade, all from one brand.
2. Regular/small box is a separate 10-piece pack. Existing master item PACK_BOX-STD (variant 5421) represents only this regular box.
3. One finished wall box requires 10 regular 10-piece boxes. N finished wall boxes require 10N regular boxes and 100N Nalki pieces.
4. Shade codes accepted: 1–900, 3000 Black, 3001 White, 3002 Off White.
5. Only OWN stock at NALKI and LABELING process stages is eligible for this draft. PARTY stock and FINISHED_GOODS stock are excluded.
6. One physical godown remains the warehouse model; NALKI and LABELING are process stages, not separate warehouses.

## Implementation completed
- Added app/packing_assortment_service.py.
- Replaced the old 1–20 variant/finished-box draft form with a 100-shade assortment form.
- Form requires one brand, a positive finished 100-piece box quantity, and exactly 100 unique shade codes. Codes can be pasted as comma-, space-, or newline-separated values.
- Server resolves the 100 shade codes to active Nalki variants for the selected brand; requires exactly one valid Nalki variant per shade and enough eligible OWN stock for the requested finished-box quantity for every selected shade.
- The 100 shade lines are stored in production.packing_order_items: each shade line carries N pieces for N finished boxes, with one piece of that shade per finished box. Header planned boxes = N and planned pieces = 100N.
- Regular 10-piece box requirement is calculated separately as 10N and written into the packing draft notes/audit snapshot. PACK_BOX-STD is not confused with the finished 100-piece product box.
- POST remains DRAFT-only and CSRF/permission protected. No stock reservation, issue, consumption, FG transfer, QC posting, wastage posting, labour payment, or accounting posting.
- UI explicitly shows the 10-piece regular box and 100-piece finished wall box as separate packing levels.
- Existing legacy draft service remains in code for compatibility but the active route now calls the 100-shade assortment service.

## Live master/stock findings
- All three Nalki brands have 903 active shade variants each (Golden Chain, Channel, Tailor).
- Eligible OWN stock coverage at NALKI/LABELING stages: Golden Chain 1 shade / 903 with 23 pieces; Channel 0 shades; Tailor 0 shades.
- Thus current stock cannot make a 100-unique-shade assortment box.
- A controlled service validation for Golden Chain shades 1–100 correctly rejected the draft because 99 selected shades had insufficient OWN stock. No packing order was inserted.
- Post-validation counts unchanged: packing_orders=2, packing_order_items=4, packing_order_status_history=0.

## Validation
- Python compilation passed for app/main.py and app/packing_assortment_service.py.
- Packing tests: 25/25 passed.
- Full test suite: 153/153 passed.
- Jinja packing template compiled successfully.
- Live form-data query returned all three brands and correct OWN stock coverage.
- ERP health: app=ok, database=true.
- No schema, master data, stock balances, ledger, roles, permissions, existing packing orders, labour rows, posted FG transfers, or accounting entries changed.

## Remaining work / blockers
1. Build the separate random 100-piece usable/rejected-shade workflow. It must preserve OWN/PARTY ownership and source lineage; do not treat usable rejected shades as wastage.
2. Add source-line traceability from Nalki production output and outside-labeling returns before stock movement can be enabled.
3. Confirm and implement the separate finished 100-piece box master item only through approved master-data configuration; do not reuse PACK_BOX-STD.
4. Add regular-box material issue, good/damaged empty regular-box returns, actual material usage/wastage, Nalki-only packing theka, QC, and controlled FG transfer only after traceability and packaging master rules are ready.

No database/schema or operational stock/accounting data was changed in this phase.

## Live application activation
- Restarted the local Uvicorn process so the new assortment route and template are loaded by the live application.
- Fresh live checks after restart: /health returned app=ok, database=true; /openapi.json confirmed GET and POST /modules/packing/new.
- No database or stock changes were made during restart.
