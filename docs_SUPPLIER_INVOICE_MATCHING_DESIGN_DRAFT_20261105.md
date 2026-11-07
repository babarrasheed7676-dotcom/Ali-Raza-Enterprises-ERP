# Supplier Invoice Registration & GRN Matching — Design Draft
Date: 05-Nov-2026
Status: DESIGN ONLY — NOT APPROVED FOR IMPLEMENTATION

## 1. Current verified application behavior

- GRN DRAFT stores supplier invoice number/date as optional header metadata.
- There is no independent supplier invoice document lifecycle or invoice table in the inspected purchasing schema.
- Duplicate supplier invoice checks are not present in the GRN draft validation path.
- GST selection is encoded in header remarks as `[GST:WITH]` or `[GST:WITHOUT]`.
- GRN approval creates one linked inward inventory stock document and approves it in the same database transaction.
- GRN approval calculates stock landed cost as line base less line discount and allocated header discount, plus allocated freight and other charges. GST is excluded from inventory cost.
- GRN approval does not create a supplier payable or GL journal.
- GRN posting posts the linked stock document, updates PO received quantities, and changes the GRN status in one transaction. It still does not create a supplier invoice or GL payable.
- Current live company has no posted GRN or posted purchase return, so the flow has no real posted purchase transaction to reconcile.

## 2. Proposed document model (requires schema design/approval)

Supplier Invoice should be a distinct financial document, separate from the physical Goods Receipt:
- Invoice header: company, supplier, supplier invoice number/date, currency, exchange rate, invoice totals, tax totals, status, approval/posting metadata, duplicate fingerprint.
- Invoice lines: item/service, quantity, unit, rate, discount, tax code/rate/amount, invoice line total, matched quantity/value.
- Matching bridge: invoice line ↔ one or more GRN lines, matched quantity and matched value.
- Evidence: supplier invoice attachment/reference and tax evidence metadata, subject to file security and retention policy.
- All foreign keys company-scoped; supplier ownership must match company.

## 3. Duplicate and matching controls

- Duplicate invoice key should be based on company + supplier + normalized supplier invoice number; date and gross amount should be additional duplicate-warning signals, not a way to bypass a duplicate number.
- Normalize invoice number conservatively (trim whitespace, case-fold only if owner approves); preserve original printed number.
- Block exact duplicate posted invoices. For DRAFT duplicates, warn/block according to an approved workflow.
- Support one invoice matching multiple GRNs and one GRN matched by multiple invoices (partial billing), with quantity/value ceilings.
- Enforce matched quantity <= posted GRN received quantity; enforce cumulative matched quantity <= GRN quantity.
- Invoice value variance thresholds require approval; never silently overwrite GRN stock cost.
- Supplier credit notes must reference the invoice and/or receipt and reverse the corresponding payable/tax treatment.

## 4. Proposed accounting sequence — options, not policy

Option A — accrue at GRN:
- At approved/posted receipt: Dr Inventory (net eligible stock cost), Cr GRNI.
- At supplier invoice posting: Dr GRNI, Dr eligible Input GST, Cr Supplier Payables.
- Invoice/GRN price or quantity variance goes to an approved variance account under a defined threshold policy.

Option B — recognize payable only at invoice:
- At GRN: inventory receipt and quantity/cost valuation are operational only; no supplier payable journal yet.
- At supplier invoice posting: Dr Inventory/approved variance (for eligible net costs), Dr eligible Input GST, Cr Supplier Payables.
- Requires robust GRN-to-invoice matching and a defined accounting treatment for received-but-not-invoiced stock at period end.

Option C — direct purchase invoice without GRN:
- Only for approved non-stock or explicitly permitted direct purchases.
- Stock items must still receive an inward stock document; no invoice-only bypass of inventory controls.

Owner/accountant must select the accrual method and approve tax eligibility, account codes, variance handling, period-end accrual, and invoice matching tolerances before implementation.

## 5. Mandatory safeguards before implementation

- No automatic journal until fiscal year and period exist and are OPEN.
- Use atomic transactions for invoice, matching, payable journal, audit log and status transitions.
- Idempotency key and unique constraints prevent duplicate posting.
- No silent editing/deletion of posted invoice, GRN or journal; corrections through controlled credit/debit notes and reversals.
- Approval and posting must be separate actions with explicit permissions and CSRF checks.
- Party balances derive from posted subledger documents/journals, not free-text values.
- PARTY-owned materials are not treated as ARE purchases or ARE inventory assets.
- Single physical godown remains the warehouse; process stage is not another warehouse.
- Tax must be structured and backed by supplier invoice evidence; a free-text GST choice is insufficient.
- Foreign currency needs an approved exchange-rate source/date, base-currency storage, rounding, and FX variance policy.

## 6. Current decision status

No option selected. No GRNI/Input GST account created. No schema, data, financial records, permissions, or posting behavior changed. This document is a review draft only.