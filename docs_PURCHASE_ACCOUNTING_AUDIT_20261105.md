# Purchase Accounting Readiness Audit
Date: 05-Nov-2026
Company: ARE Faisalabad (company_id=1, PKR)

## Safety and scope
Read-only review of the existing Purchasing service, Inventory posting function, Chart of Accounts, and live company data. The only code changes in this phase are a read-only readiness report, its template section, and tests. No database records, account masters, journal entries, fiscal years, periods, triggers, or posting functions were changed. Automatic GL posting remains disabled.

## Verified current Chart of Accounts
- 2211 Supplier Payables exists and is structurally valid as an active, non-group liability control account with CREDIT normal balance.
- 2221 Sales Tax Payable exists as a liability control account with CREDIT normal balance. It is an output-tax liability, not an input-tax receivable asset.
- No active asset/debit Input GST Receivable, Input Tax, GST Receivable, or Sales Tax Receivable account was found.
- No dedicated Goods Received Not Invoiced (GRNI) / Goods Received Not Invoiced liability account was found.
- Do not create or repurpose accounts without a separately approved accounting master-data change.

## Goods Receipt (GRN) behavior in current code
1. GRN draft captures line quantities, unit prices, line discounts, GST amounts, header discount, freight, other charges, supplier and optional PO.
2. Supplier GRN accepts OWN stock only. PARTY-owned materials are rejected from this supplier receipt path.
3. Receipt warehouse defaults to location id 9, consistent with the one-godown design; it is not a process-stage warehouse.
4. On approval, line discounts and allocated header discounts reduce inventory cost. Freight and other charges are allocated by net line value and increase landed inventory cost.
5. GST is explicitly excluded from stock cost under the assumption that it is recoverable input GST. The approval audit payload labels it as recoverable input GST.
6. The live COA has no valid Input GST Receivable asset account. Therefore, current code's recoverability assumption cannot yet be represented by a valid GL debit account. If the tax is not recoverable, excluding it from inventory cost may understate stock value.
7. The purchase receipt header has no currency_code or exchange_rate column. Purchase Orders do have currency_code. Foreign-currency PO/GRN conversion behavior must be resolved before GL posting.
8. Approval creates one linked APPROVED inventory stock document, atomically with GRN approval. Posting then updates PO received quantities and inventory stock through inventory.post_stock_document in one transaction.
9. No journal entry or journal line is created in the inspected GRN approval/posting path.

## Purchase Return behavior in current code
1. Return drafts are linked to original GRN lines and limited to the remaining received quantity.
2. Supplier Purchase Returns currently support OWN stock only.
3. Return approval creates one linked outward stock document; return posting calls inventory.post_stock_document.
4. Return draft monetary value is derived from original receipt unit price, proportional discount and proportional tax.
5. Inventory outward posting values the returned quantity at the current moving-average cost from stock_balances, not necessarily the original receipt price.
6. Therefore the supplier credit-note amount and inventory cost relieved can differ. The business needs an approved price/stock variance policy and approved tax-credit-note treatment.
7. No journal entry or journal line is created in the inspected Purchase Return approval/posting path.

## Live database findings (read-only)
- Purchase Receipts: 0 records.
- Purchase Returns: 0 records.
- Posted GRNs: 0.
- Posted Purchase Returns: 0.
- Purchase Orders: 0 (no currency groups returned).
- Supplier Payables 2211: structurally valid.
- Input GST Receivable: missing.
- GRNI: missing.
- Journal entries: 0.
- Journal lines: 0.
- Fiscal years: 0.
- Accounting periods: 0.

There are no live posted purchasing documents available for end-to-end GL reconciliation or real transaction sampling.

## Accounting policy choices required before implementation
### Option A — invoice and goods receipt recognized together
If a valid supplier tax invoice is available and the supplier payable is recognized at GRN posting:
- Dr inventory accounts for eligible OWN stock at approved landed cost
- Dr approved input-tax receivable only where tax is legally recoverable and supported by invoice evidence
- Cr supplier payable control (2211) for the recognized supplier liability
This option requires explicit invoice evidence, tax recoverability rules, supplier subledger integration, and account mapping.

### Option B — goods received before supplier invoice
If stock is recognized before the supplier invoice:
- At GRN: Dr inventory at approved landed cost; Cr an approved GRNI liability account.
- At supplier invoice: Dr GRNI; Dr eligible input-tax receivable; Cr supplier payable.
This option requires a dedicated GRNI account and matching/clearing controls.

### Non-recoverable tax
If tax is not recoverable, it must not be posted to an input-tax asset. The owner/accountant must approve whether it is capitalized into inventory cost or expensed, with consistent item and tax treatment.

### Purchase Return
- Inventory credit must use the inventory valuation method used by the stock ledger (currently moving average).
- Supplier credit must follow the supplier credit note / payable policy.
- Any difference between supplier credit and inventory cost relieved needs a specifically approved price variance account/rule.
- Input tax reversal must only occur where the original tax was recognized as recoverable and a valid credit note supports reversal.

## Next safe implementation sequence
1. Owner/accountant selects Option A or Option B for receipt vs invoice timing.
2. Confirm when GST is recoverable, required supplier tax-invoice evidence, and treatment of non-recoverable tax.
3. Approve GRNI and Input Tax Receivable accounts as separate master-data changes if needed.
4. Confirm foreign currency PO policy and where exchange rates are stored/approved.
5. Approve Purchase Return price variance and tax reversal policy.
6. Confirm supplier subledger posting, invoice matching, duplicate prevention, reversal, and audit requirements.
7. Verify active fiscal year and open period controls before any journal posting.
8. Implement atomic, idempotent GL posting only after all above controls pass.

## Current implementation status
- Read-only Purchase Accounting Readiness panel added to Accounting Setup Readiness.
- It validates the existing Supplier Payables account, identifies missing Input Tax Receivable and GRNI accounts, warns that 2221 is output-tax liability only, and shows purchasing document counts and policy blockers.
- Candidate inventory account mapping and all transaction-type policy blockers remain visible.
- Automatic purchase/inventory GL posting remains disabled.

## 05-Nov-2026 follow-up — invoice evidence and schema audit

A second read-only inspection of the live PostgreSQL catalog confirmed:

- No separate supplier purchase-invoice register/table exists in the inspected `purchasing`, `accounting`, or `master` schemas. Supplier invoice number and date are optional metadata columns on `purchasing.purchase_receipts` only.
- There is no independent supplier-invoice approval, invoice posting, GRN-to-invoice matching, or invoice duplicate-control lifecycle in the inspected purchasing schema.
- The GST choice is stored in the GRN `remarks` text marker (`[GST:WITH]` / `[GST:WITHOUT]`), not a dedicated structured column.
- Selecting With GST does not require a supplier invoice number or invoice date in the current draft validation.
- Purchase Orders contain a currency code, but Purchase Receipts contain neither currency code nor exchange rate. A foreign-currency PO therefore cannot safely be assumed to carry a validated converted local-currency GRN amount.

### Additional implementation blockers surfaced

1. Do not recognize recoverable input GST merely because the GRN GST choice says With GST. Require approved tax eligibility and supplier invoice evidence.
2. Before invoice-based supplier payable posting, define a supplier invoice register/matching lifecycle, duplicate invoice controls (supplier + invoice number/date), and partial invoice / multiple GRN matching rules.
3. Persist tax treatment as structured data only through an approved schema change; do not silently reinterpret the existing remarks marker.
4. Resolve foreign-currency conversion source, rate date, rounding, and realized/unrealized difference treatment before PO-to-GRN accounting.

The Accounting Setup Readiness panel now explicitly lists the missing invoice register/matching lifecycle and the free-text GST marker/invoice-evidence gap. A focused unit test asserts both blockers. No schema, records, roles, journal entries, or posting behavior were changed.