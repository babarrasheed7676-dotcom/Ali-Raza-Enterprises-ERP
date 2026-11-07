# Single Physical Godown — Read-only Stock Reconciliation
Date: 05-Nov-2026
ERP working copy: ARE ERP SAFE WORKING COPY CSS FIXED 18-Oct-2026

## Scope and safety
- Read-only PostgreSQL transaction; no data, schema, location, stock balance, ledger, permission or user changes.
- The approved business rule remains one physical godown. Nalki, Labeling, Packing, Finished Goods, Dispatch, Dyeing, Big Cone and Baby Cone are workflow/process stages, not separate physical warehouses.
- Nine legacy paired records exist in core.locations and inventory.locations. All nine are active and allow stock.

## Legacy location stock summary
| Legacy location | Balance rows | Variants | Quantity | Value PKR |
|---|---:|---:|---:|---:|
| RAW_STORE | 0 | 0 | 0 | 0 |
| DYEING | 0 | 0 | 0 | 0 |
| BIG_CONE | 0 | 0 | 0 | 0 |
| BABY_CONE | 0 | 0 | 0 | 0 |
| NALKI | 2 | 2 | 118 | 4,366.666669 |
| LABELING | 1 | 1 | 5 | 666.666665 |
| PACKING | 0 | 0 | 0 | 0 |
| FG_STORE | 2 | 2 | 400 | 4,000.000000 |
| DISPATCH | 0 | 0 | 0 | 0 |
| **Total** | **5** | **3** | **523** | **9,033.333334** |

## Nonzero stock detail
| Item variant | Legacy location | Process stage | OWN qty | Average unit cost | Value PKR |
|---|---|---|---:|---:|---:|
| NALKI-GOLDEN_CHAIN-1 | NALKI | NALKI | 18 | 131.481482 | 2,366.666669 |
| NALKI-GOLDEN_CHAIN-1 | LABELING | LABELING | 5 | 133.333333 | 666.666665 |
| NALKI-GOLDEN_CHAIN-1 | FG_STORE | FINISHED_GOODS | 100 | 10.000000 | 1,000.000000 |
| NALKI-CHANNEL-1 | FG_STORE | FINISHED_GOODS | 300 | 10.000000 | 3,000.000000 |
| NALKI_TUBE-STD | NALKI | NULL (missing stage) | 100 | 20.000000 | 2,000.000000 |

Important:
- NALKI_TUBE-STD is a distinct item code, not the NALKI finished product. Its 100 pieces have NULL process_stage_id; do not classify them as Nalki output or packing input without a separately approved master/process mapping.
- The 100 Golden Chain pieces and 300 Channel pieces in FG_STORE are already FINISHED_GOODS and must not be repacked as Nalki input.
- Only 18 Golden Chain pieces in NALKI and 5 in LABELING currently meet the Packing Phase 1B source-stage rule; total 23, less than one 100-piece finished wall box.
- The 100 NALKI_TUBE pieces are not included in Nalki finished-product eligibility.

## Ledger evidence
- inventory.stock_document_lines: 12 lines across 3 legacy locations.
- Aggregate ledger quantity_in: 536; quantity_out: 13.
- Posted document groups observed: PRODUCTION_OUTPUT (2 documents / 2 lines), SALES_DISPATCH (3 / 3), STOCK_OPENING (2 / 2), STOCK_TRANSFER (1 / 2), TEST_INWARD (2 / 2), TEST_OUTWARD (1 / 1).
- Historical stock transfer TEST-TRANSFER-001 moved 5 Golden Chain pieces from NALKI stage/location to LABELING stage/location. Do not rewrite this posted document.
- The posted output documents PO-00001 and PO-00002 placed 100 Golden Chain and 300 Channel pieces into FINISHED_GOODS.

## Safe implementation implications
1. Do not consolidate legacy location rows by directly changing location_id in existing balances or ledger documents.
2. A future single-godown migration must preserve the process_stage_id and ownership/batch/cost dimensions, reconcile each item and total value, and use an approved, auditable inventory transfer/migration document.
3. The 100 NALKI_TUBE pieces with NULL process stage need classification by item/master business meaning before any workflow consumes them.
4. The four empty legacy locations can be reviewed separately; do not deactivate them until all FK dependencies, historical references, permissions and reports have been checked.
5. No existing posted FG transfers or other posted inventory documents were changed.

## Conclusion
The current balance data is concentrated in NALKI, LABELING and FG_STORE legacy locations, but the physical single-godown target cannot be achieved safely by relabelling records. It requires a separate controlled migration plan with process-stage preservation and full ledger reconciliation.