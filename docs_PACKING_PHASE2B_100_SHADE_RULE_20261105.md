# Nalki Packing — Corrected Two-Level Box Rule
Date: 05-Nov-2026
Backup: BACKUP_PACKING_PHASE2B_100_SHADE_RULE_20261105

## Confirmed historical business rules recovered from prior user discussions
1. Regular / small box is 10 Nalki pieces. Existing master item is PACK_BOX / PACK_BOX-STD, variant ID 5421, unit PCS. This is the 10-piece regular box; it is NOT the 100-piece finished box.
2. Finished 100-piece wall box is a separate finished-product packing level. It is made from finished Nalki pieces and is not the same SKU as PACK_BOX-STD.
3. A 100-shade assortment finished box contains 100 unique shades, one piece of each shade, from one brand. For N finished boxes, each of the 100 selected shade variants must supply N pieces.
4. Each 100-piece finished box consumes 10 regular 10-piece boxes. Example: 120 finished boxes = 1,200 regular boxes + 12,000 Nalki pieces.
5. Party-rejected Nalki shades that are still usable are not wastage; they may be reused in a separate random 100-Nalki box workflow. This must remain distinct from the 100-unique-shade assortment workflow and preserve source/ownership traceability.
6. Nalki packing is its own process; Packing is not a standalone factory department. Baby Cone packing/salary/theka must not be mixed into Nalki packing.

## Verified master data
- PACK_BOX item ID 7; variant ID 5421; variant code PACK_BOX-STD; name Packing Box - Standard; unit PCS; active.
- This existing variant is now formally mapped in service constants to the regular 10-piece small box.
- No separate 100-piece finished box packaging master item/variant was found in the current database search. No master data was created or modified.

## Code added in this phase
- REGULAR_SMALL_BOX_VARIANT_CODE = PACK_BOX-STD.
- calculate_finished_box_material_requirements() calculates:
  - 1 finished 100-piece box = 10 regular boxes + 100 Nalki pieces.
  - 120 finished boxes = 1,200 regular boxes + 12,000 Nalki pieces.
- validate_finished_box_shade_composition() requires exactly 100 unique shade IDs, unique variants, a single brand, and at least one piece of every selected shade per finished box. For N finished boxes it checks N OWN source pieces for each shade.
- Added tests for the 100-shade composition, duplicate shades, mixed brands, missing shade rows, insufficient per-shade stock, and the 120-box material calculation.
- Existing old draft normalization/form has NOT yet been switched to the 100-shade composition flow. Do not use the old 20-line draft form to create an operational packing plan; it still assumes a per-variant 100-piece quantity and is not suitable for a 100-unique-shade assortment.
- No routes, posting, inventory issue, stock transfer, FG receipt, labour payment, or accounting posting were enabled in this phase.

## Current stock constraint
Current verified stock remains: Golden Chain has only 18 pieces at NALKI stage and 5 at LABELING; Channel's 300 pieces are already FINISHED_GOODS. Thus current live stock cannot make a complete 100-unique-shade box. No stock was reserved or consumed.

## Next implementation requirements
1. Redesign the draft UI and service around 100 shade lines per assortment box, with one piece per shade per finished box, while keeping the 10-piece regular boxes as a separate material requirement.
2. Create a separate 100-piece finished-box packaging/product master only after an approved code/name/unit decision; do not reuse PACK_BOX-STD for it.
3. Implement the random usable/rejected-shade reuse workflow separately. Usable rejected shades are not wastage and must retain OWN/PARTY ownership and source lineage.
4. Link Nalki production output and outside-labeling return lines to each packing shade line, preserving one physical godown and process-stage dimensions.
5. Add empty regular-box returns, actual material usage/wastage, Nalki-only theka labour, QC and approved FG transfer only after source traceability is in place.

## Validation
- Python compilation passed.
- Packing + configuration tests: 51/51 passed.
- No database schema or rows, stock, permissions, roles, existing labour approvals, posted transfers, or accounting entries changed.