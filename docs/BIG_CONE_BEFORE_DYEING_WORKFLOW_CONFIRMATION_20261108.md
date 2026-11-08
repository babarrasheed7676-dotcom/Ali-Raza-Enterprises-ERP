# Big Cone Before Dyeing — Confirmed Workflow Addendum
Date: 8 November 2026

## Authority and correction
This addendum records the user's explicit correction and approval in the 8 November 2026 conversation. It supersedes the earlier assumption that Big Cone winding follows Dyeing, and supersedes the unresolved-flow wording in REWINDING_WORKFLOW_READ_ONLY_AUDIT_20261108.md for the Big Cone process specifically.

## Confirmed factory purpose
Big Cone winders operate BEFORE dyeing. Their job is to wind/rewind purchased raw yarn onto perforated jaali/dye cones, preparing packages for the factory dyeing machines. The factory-specific target is exactly 1.25 KG per dye cone.

The perforations allow dye liquor to circulate through the yarn package. The technical principle is consistent with package-dyeing practice; 1.25 KG is the user's factory-specific machine/package setting, not a universal web-derived standard.

## Confirmed process sequence
PURCHASED RAW YARN at RAW_STORE / PURCHASE
  -> BIG_CONE winding/rewinding
  -> 1.25 KG perforated jaali/dye cones
  -> DYEING

The Big Cone output is prepared for DYEING. This process does not imply a second warehouse: all stock remains in the factory's single physical godown, while PURCHASE, BIG_CONE and DYEING are process-stage dimensions.

## Source-code verification (read-only)
The current safe working copy was inspected without changing application code or business data:
- app/big_cone_draft_service.py defines DESTINATIONS = {"DYEING"}.
- normalize_big_cone_lines() requires output KG = output cone count x 1.25 KG and rejects any destination other than DYEING.
- get_big_cone_draft_form_data() resolves active PURCHASE, BIG_CONE and DYEING process-stage masters; purchased OWN Yarn at RAW_STORE/PURCHASE is selected as the input source.
- create_big_cone_draft() validates purchased OWN Yarn stock at RAW_STORE/PURCHASE and records Big Cone input/output lineage.
- app/production_service.py orders the read-only workflow display as PURCHASE -> BIG_CONE -> DYEING -> BABY_CONE -> NALKI -> LABELING -> PACKING -> FINISHED_GOODS. It sorts the display list; this is not a write to master sequence data.
- The application health endpoint returned app=ok and database=true during this check.

## Important boundary
This confirms the existing Big Cone application logic is aligned with the user's stated pre-dyeing process. It does not establish that machines/departments are configured or that any Big Cone production order has been saved. Do not create test production records or change stock/ledger data for verification.

## Previous audit clarification
The earlier rewinding audit's statement that the revised flow was unavailable is now outdated for the Big Cone-to-Dyeing handoff. The separate generic rewinding tables/workflow gap remains a distinct issue; do not conflate it with Big Cone winding or assume that a separate generic rewinding workflow has been implemented.

## Change scope
Documentation-only addendum. No application code, database schema, master data, production records, permissions, stock, ledger, or server process was modified.
