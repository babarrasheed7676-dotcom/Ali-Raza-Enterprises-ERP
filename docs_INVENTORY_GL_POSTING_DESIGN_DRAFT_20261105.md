# Inventory-to-GL Posting Design — Read-only Audit Draft
Date: 05-Nov-2026
Company: ARE Faisalabad (company_id=1, PKR)

## Purpose and safety status
This document records a proposed design based on inspected application code and live database metadata. It is **not an approved accounting policy and is not implemented**. No database schema, records, triggers, functions, journals, fiscal years, or periods were changed during this review. No automatic posting should be enabled from this draft.

## Verified architecture
- `inventory.post_stock_document()` posts inventory quantities/costs to stock balances and stock ledger; inspected implementation does not create accounting journal entries.
- No database trigger was found linking stock documents/ledger to accounting journal entries/lines.
- Purchasing receipt and purchase-return posting services call `inventory.post_stock_document()`; no accounting journal creation was found in those paths.
- Stock lines carry quantity_in, quantity_out, unit_cost, total_cost, ownership_type_id, owner_party_id, process_stage_id, item_variant_id and location_id.
- One physical godown remains the operational warehouse model; process_stage_id is a workflow dimension, not another warehouse.
- PARTY-owned stock must not be included in ARE-owned inventory assets or posted as ARE inventory. OWN stock is eligible for company inventory accounting subject to validation.
- Sales dispatch is a stock movement only; it must not create a sales invoice or revenue entry. A separate cost-of-sales/inventory journal may be required for OWN stock once the accounting policy and posting controls are approved.

## Existing account candidates (live COA)
| Account | Name | Use candidate / limitation |
|---|---|---|
| 1241 | Raw Yarn / Thread Inventory | Candidate for YARN |
| 1242 | Dyes & Chemicals Inventory | Candidate for DYE_CHEM |
| 1243 | Cones & Tubes Inventory | Candidate for CONE and TUBE |
| 1244 | Production WIP Inventory | Candidate WIP/control bucket; stage allocation rules still needed |
| 1245 | Nalki Inventory | Candidate for NALKI |
| 1246 | Packing Material Inventory | Candidate for PACK_MAT |
| 1247 | Finished Goods Inventory | Candidate for FG |
| 1248 | Fuel Inventory | Candidate for FUEL |
| 1249 | General Stock Inventory | Candidate only for items explicitly classified as general stock; LABEL needs a confirmed policy |
| 2211 | Supplier Payables | Existing supplier control; does not by itself resolve GRNI/receipt accrual policy |
| 5110 | Nalki Cost of Goods Sold | Candidate for Nalki dispatch cost |
| 5120 | Yarn / Thread Cost of Goods Sold | Candidate for yarn/thread dispatch cost |
| 5130 | Other Product Cost of Goods Sold | Candidate for other finished goods dispatch cost |
| 5190 | Inventory Cost Adjustments | Candidate for approved stock valuation adjustment differences |
| 2221 | Sales Tax Payable | This is a liability, not verified input-tax receivable; do not use for purchase input tax |
| 3210 | Retained Earnings | Not an opening-stock clearing account; do not substitute |

All accounts above exist and were active in the inspected company COA. Candidate use is not approval to post.

## Inventory categories observed
| Category code | Name | Current item count | Candidate account |
|---|---|---:|---|
| YARN | Yarn / Thread | 1 | 1241 |
| DYE_CHEM | Dyes & Chemicals | 1 | 1242 |
| CONE | Cones | 2 | 1243 |
| TUBE | Nalki Tubes | 1 | 1243 |
| NALKI | Nalki | 1 | 1245 |
| PACK_MAT | Packing Material | 2 | 1246 |
| FG | Finished Goods | 0 | 1247 |
| FUEL | Fuel | 1 | 1248 |
| GENERAL | General Stock | 0 | 1249 |
| LABEL | Labels | 1 | **Unresolved** — confirm whether labels are packing material or general stock |

These are candidate classifications. Production-stage and WIP treatment, mixed/combined materials, and any category exceptions require owner/accountant approval.

## Transaction-to-GL design matrix (not implemented)
| Transaction type | Candidate accounting treatment for OWN stock | PARTY stock | Readiness / blocker |
|---|---|---|---|
| PURCHASE_RECEIPT | Dr relevant 124x inventory; Cr supplier/GRNI only under an approved invoice/accrual policy | No ARE asset entry | **Blocked:** no dedicated GRNI account identified; supplier payable vs receipt accrual, invoice timing, input-tax and landed-cost allocation unresolved |
| PURCHASE_RETURN | Cr relevant 124x inventory; Dr supplier payable/credit balance when supplier credit is recognized | No ARE asset entry | **Blocked:** no posted purchase-return sample; credit-note and supplier-balance handling not yet proven end-to-end |
| PRODUCTION_CONSUMPTION | Dr WIP 1244 or approved process cost bucket; Cr source 124x inventory | Exclude PARTY material from ARE asset journal; track party settlement/cost separately | **Blocked:** production costing, stage/WIP allocation, ownership and cost absorption rules need validation |
| PRODUCTION_OUTPUT | Dr destination 124x inventory; Cr WIP 1244, with cost transfer at validated actual cost | Do not capitalize party-owned output as ARE inventory | **Blocked:** output-cost roll-up and process-stage mapping must be validated |
| SALES_DISPATCH | Dr product-specific COGS (5110/5120/5130); Cr relevant inventory 124x, for OWN stock only | No ARE inventory/COGS for party-owned stock; party settlement rules separate | **Conditional:** dispatch is not an invoice; confirm item-to-COGS map, cost source and reversal/return handling |
| STOCK_TRANSFER | No net GL when OWN asset class/value is unchanged; if inventory class changes, Dr destination 124x / Cr source 124x | No ARE asset entry | **Conditional:** confirm cost preservation, location/stage semantics and transfer pairing |
| STOCK_ADJUSTMENT | Increase: Dr inventory / Cr approved adjustment gain; decrease: Dr 5190 / Cr inventory, subject to approved policy | No ARE asset entry | **Blocked:** gain/loss counterpart policy and approval thresholds not confirmed |
| STOCK_OPENING | Dr relevant 124x / Cr a specifically approved opening-balance clearing account | Party balances excluded from company inventory | **Blocked:** no dedicated opening-stock clearing account identified; never substitute retained earnings |
| STOCK_RECLASSIFICATION | Reclass between relevant 124x accounts only when OWN inventory classification changes; zero total asset effect | OWN↔PARTY ownership change requires separate approved settlement/liability policy; not a normal zero-entry | **Blocked:** ownership transition, process-stage and category-change rules need approval |

## Live evidence and caveats
- Current OWN operational stock snapshot: PKR 9,033.333334.
- Inventory control account net (1241–1249): PKR 0.00; observed difference PKR 9,033.333334.
- 11 posted stock documents were counted in the live company dataset. Their document numbers include TEST records; do not describe all 11 as genuine production transactions.
- The posted records include test stock openings, production outputs, sales dispatches and a stock transfer. No posted purchase receipt or purchase return was found.
- One posted sales-dispatch sample used a test document number; no sales invoice is implied by dispatch.
- The current operational stock snapshot is not a historical opening-stock valuation.
- No journal entries, journal lines, fiscal years or accounting periods were present at the last read-only verification.

## Mandatory gates before implementation
1. Owner/accountant approves each transaction's debit/credit policy, especially GRNI, input tax, production WIP, stock adjustment, opening stock and PARTY ownership.
2. Confirm category-to-inventory-account mapping, including LABEL and any mixed-fibre/combined production items.
3. Confirm transaction cost source, landed-cost/tax treatment, reversals, returns, partial receipts and duplicate prevention.
4. Require an active fiscal year and open accounting period; fail closed when absent.
5. Post inventory movement and its GL journal atomically in one database transaction, with immutable source-document link and idempotency protection.
6. Validate balanced journals, OWN/PARTY segregation, account active/control status, currency, audit log and reversal workflow.
7. Backfill existing posted stock only through a separately approved, reconciled opening/conversion plan. Never auto-journal historical test documents.

## Next safe implementation step
Build a read-only mapping-readiness validator and test fixtures around the approved rules after approval. Until then, keep inventory-to-GL auto-posting disabled and retain the mismatch warning on Accounting Setup Readiness.
