# Dyeing → Baby Cone Handoff — Confirmed Integration Blocker
Date: 8 November 2026
Scope: Read-only source and database inspection.

## Confirmed stage master
Company 1 active stages are stored in the correct process order:
1 PURCHASE — Purchased Yarn / Raw Material
2 BIG_CONE — Big Cone
3 DYEING — Dyeing
4 BABY_CONE — Baby Cone
5 NALKI — Nalki Production
6 LABELING — Labeling
7 PACKING — Packing
8 FINISHED_GOODS — Finished Goods

The user's corrected sequence BIG_CONE before DYEING is therefore reflected in stored master sequence numbers, not only the dashboard display. Single physical godown rule remains unchanged.

## Confirmed Big Cone function
Big Cone prepares purchased raw yarn on perforated jaali/dye cones at the factory's specified 1.25 KG per cone, before dyeing. Big Cone service's output destination allow-list is DYEING. This is consistent with the confirmed stage sequence.

## Dyeing source and output
- Dyeing form selects OWN raw yarn stock at RAW_STORE / BIG_CONE.
- Dyeing DRAFT service writes DYED_THREAD output lines at RAW_STORE / DYEING stage.
- Dyeing source file explicitly says DRAFT only and no stock posting.
- Dyeing approval-readiness function is read-only and describes itself as preflight for a future approval/post workflow.
- No completed Dyeing stock-posting/approval handoff was established in the inspected application routes/services.

## Baby Cone source mismatch
- Baby Cone preflight currently queries POSTED production.big_cone_output_lines with destination_type='BABY_CONE' at RAW_STORE / BIG_CONE.
- Big Cone service only permits destination_type='DYEING'. It does not create BABY_CONE-destination output lines.
- Dyeing's DYED_THREAD output lines are the logically relevant post-dyeing material, but the current Baby Cone preflight does not query them.
- Therefore current source preflight cannot represent the confirmed Big Cone → Dyeing → Baby Cone chain correctly.
- Do not fix by allowing BABY_CONE as a direct Big Cone destination; that would bypass Dyeing and contradict the factory's confirmed process.

## Setup and data state
Read-only DB check:
- All 8 process stages above are active and correctly sequenced.
- Active machines: 0.
- Active departments: 0.
- No Dyeing, Big Cone or Baby Cone order status rows were present at check time (the respective order tables returned no grouped status rows).
- Seven Baby Cone tables remain empty per the earlier audit.

## Correct implementation architecture (design recommendation, not yet implemented)
1. Keep Big Cone output at DYEING stage (1.25 KG jaali/dye cones).
2. Complete Dyeing's separate DRAFT → approval → posting workflow. Posting must consume Big Cone stage stock and create DYED_THREAD stock at DYEING stage with exact batch, shade, variant, ownership and cost lineage.
3. Change Baby Cone source preflight to select eligible POSTED Dyeing output lines / DYEING-stage stock, not Big Cone output lines.
4. Add immutable source_dyeing_output_line_id (or an equivalent rigorously enforced source reference) to Baby Cone material lines; preserve batch, item variant, single location, ownership/party, stage, unit cost and exact quantity lineage.
5. Prevent double allocation across DRAFT/APPROVED Baby Cone orders and lock exact stock rows at approval/posting.
6. Only then implement Baby Cone DRAFT → separate approval → posting, including approved measurement profile snapshots, salary-based labour/overheads, verified loss/reconciliation, audit log and atomic stock documents.
7. Do not activate production entry until required departments/machines and master configuration are genuinely ready.

## Safety boundary
Read-only audit and documentation only. No code, schema, master data, roles, permissions, stock, ledger, production orders or server processes were changed. No dummy production records were created.
