# Purchase Return & Supplier Credit Note Audit
Date: 05-Nov-2026
Status: Source + catalog audit; no application or database mutation.

## 1. Scope
Reviewed:
- app/purchasing_service.py: return form data, draft creation, approval and posting.
- app/main.py: return create, approve and post routes.
- PostgreSQL catalog for purchasing.purchase_returns and purchasing.purchase_return_lines.
- Definitions of inventory.approve_stock_document and inventory.post_stock_document.
All database catalog/data queries ran inside explicit READ ONLY transactions.

## 2. Current operational flow
- Return creation requires 1–10 lines and a selected original GRN.
- Only a POSTED GRN with a warehouse can be returned.
- Supplier is inherited from the GRN and must still be active in the same company.
- Return lines must refer to lines belonging to that GRN; duplicate line IDs are rejected.
- Only OWN stock (ownership_type_id=1, owner_party_id NULL) is accepted.
- Return quantity must be positive, within precision limits and no greater than remaining received quantity.
- Remaining quantity includes all DRAFT, APPROVED and POSTED returns, so an unposted draft reserves quantity.
- A transaction advisory lock keyed by company + original GRN serializes returns against that receipt.
- Original line unit, item, batch, ownership and process stage are copied into the return.
- Original line discount and tax are apportioned by returned quantity; header discount is allocated by net line value.
- Return document is created as DRAFT and audited in the same transaction.

## 3. Approval and posting controls
- Create route requires purchasing.create and validates form content type, request size, parser field count and CSRF cookie/form token.
- Approve route requires purchasing.approve + inventory.approve and validates CSRF.
- Post route requires purchasing.post + inventory.post and validates CSRF.
- Approval re-locks the return and original GRN, verifies the GRN remains POSTED, supplier/warehouse still match, supplier and location remain active, and return lines still match original GRN line attributes.
- Approval validates total returns across DRAFT/APPROVED/POSTED do not exceed original received quantity.
- Approval creates one linked outward PURCHASE_RETURN stock document and calls inventory.approve_stock_document in the same transaction.
- Posting requires exactly one APPROVED linked stock document, then calls inventory.post_stock_document and marks the return POSTED atomically.
- Both approval and posting are idempotent for their already-completed matching state; inconsistent linked states are rejected.
- Inventory outward posting calculates cost from the current stock balance average unit cost, reduces quantity and value, writes stock ledger, and updates stock document line cost. The initial return stock-document line uses zero cost fields, but posting calculates actual moving-average cost from stock on hand. This is inventory valuation only, not GL accounting.

## 4. Schema constraints and gaps
- purchase_returns has unique (company_id, return_no); it does NOT have a unique supplier credit note key.
- supplier_credit_note_no and supplier_credit_note_date are nullable; the service does not require either to create a return.
- Live duplicate credit-note scan returned zero groups, but the table is empty; this does not prove duplicate protection.
- purchase_return_lines has unique (purchase_return_id, line_no), positive quantity and non-negative monetary checks.
- purchase_return_lines.purchase_receipt_line_id is nullable at database level even though the service requires a valid original GRN line.
- purchase_returns.purchase_receipt_id is nullable at database level even though service create/approve/post require it.
- Catalog foreign keys on return lines are single-column IDs; company scoping is enforced in application queries, not by composite tenant-scoped foreign keys.
- Live counts: 0 purchase returns, 0 return lines, 0 credit note numbers, 0 credit note dates. Therefore no live return scenario or duplicate-credit-note scenario can be exercised.
- No supplier credit-note register, independent credit-note approval, invoice matching or duplicate credit-note control exists.
- Return posting updates stock only. It does not create supplier payable credit, GL journal, input GST reversal or invoice settlement.

## 5. Important accounting blockers
1. Supplier credit note is only optional metadata on a stock-return document, not a separately controlled financial document.
2. No link to a supplier invoice exists, so return quantities/values cannot be reconciled to an invoice line or outstanding payable.
3. No accounting treatment exists for credit note amount, tax reversal, discount/freight adjustments or payable reduction.
4. Tax amounts are proportionally copied from the GRN line; eligibility and credit-note tax evidence are not validated.
5. Currency and exchange-rate handling is absent from return header.
6. No duplicate credit note constraint exists at database level.
7. No actual posted return exists to validate the full operational path.

## 6. Recommended design controls (not implemented)
- Keep physical stock return and supplier credit note as distinct but linked documents.
- Credit note should reference supplier, original invoice, relevant GRN/return and currency.
- Enforce normalized duplicate identity at database level after agreeing supplier-specific normalization and draft-vs-posted duplicate policy.
- Permit partial credit-note matching to multiple returns/invoices only through explicit quantities/amounts and a controlled allocation table.
- Validate credit note lines against posted returns and original invoice quantities; prevent over-crediting.
- Tax reversal requires verified credit note/tax evidence and approved tax rules.
- Financial posting must be a separate approved/post action with open-period validation, journal idempotency and audit trail.
- Do not create payable or GL journals until invoice lifecycle, tax treatment, FX policy, period controls and posting mappings are approved.

## 7. Conclusion
The existing Purchase Return workflow has meaningful stock and quantity controls and uses moving-average inventory cost on posting. It is not a supplier credit-note accounting workflow. Supplier credit-note uniqueness, invoice matching, tax reversal and payable/GL effects remain unimplemented. No code, schema, permissions, configuration or financial records were changed.
