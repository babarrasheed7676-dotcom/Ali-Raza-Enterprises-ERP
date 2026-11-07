# Purchasing GRN / Supplier Invoice Schema Audit
Date: 05-Nov-2026
Status: READ-ONLY AUDIT — NO DATABASE CHANGES

## Scope and method
Inspected the live PostgreSQL catalog for purchasing.purchase_receipts, purchasing.purchase_receipt_lines and purchasing.purchase_returns. Catalog queries ran inside an explicit READ ONLY transaction. Also inspected the corresponding application routes and service flow. No business rows, schema objects, indexes, permissions or configuration were changed.

## Verified receipt header structure
purchase_receipts contains:
- Company, receipt number/date, optional purchase order, supplier and status.
- Optional supplier_invoice_no and supplier_invoice_date.
- One warehouse_location_id.
- Subtotal, discount, tax, freight, other charges and grand total.
- Created/approved/posted user and timestamp fields.
- Remarks text.

It has no dedicated invoice currency or exchange-rate columns, no structured GST choice/tax evidence fields, and no separate invoice lifecycle/status.

## Verified receipt line structure
purchase_receipt_lines contains:
- Receipt and line number, optional PO line, item variant, quantity and unit.
- Unit price, discount, tax, freight, other charges and line total.
- Ownership type, optional owner party, optional batch/process stage, remarks.
- Positive quantity and non-negative monetary checks.
- Unique (purchase_receipt_id, line_no).

## Duplicate protection findings
- purchase_receipts has unique (company_id, receipt_no), but no unique constraint/index for (company_id, supplier_id, supplier_invoice_no), normalized invoice number, or invoice fingerprint.
- supplier_invoice_no is nullable; supplier_invoice_date is nullable.
- Current live table counts: 0 GRNs, 0 rows with invoice number, 0 rows with invoice date. Therefore no real duplicate scenario can be tested against current data.
- A read-only duplicate scan returned zero groups, which is expected because there are no GRNs; this is not proof that duplicate protection exists.
- purchase_returns stores optional supplier_credit_note_no and supplier_credit_note_date, but has no unique supplier credit-note key either. Only return_no is unique by company.

## Foreign keys and company scope
- Receipt header has foreign keys to company, supplier party, PO, warehouse location and user metadata.
- Receipt lines reference receipt, item variant, unit, ownership type, owner party, PO line, batch and process stage.
- The catalog constraints inspected do not establish composite company-scoped foreign keys for supplier/party/item relationships. Application-level company checks exist in the GRN draft/approval service. Future invoice matching should preserve and strengthen company scoping; do not treat a simple ID foreign key as a tenant-scope control by itself.

## Route and workflow control observations
- GRN creation is a separate DRAFT save action.
- Approval route requires purchasing.approve and inventory.approve, then validates CSRF and invokes the transactional GRN approval service.
- Posting route requires purchasing.post and inventory.post, then validates CSRF and invokes the transactional posting service.
- GRN approval creates/approves the linked inward stock document; posting updates stock and PO received quantities atomically.
- Neither approval nor posting creates a supplier invoice, supplier payable or GL journal.
- GRN metadata fields are not a substitute for a separate supplier invoice register or an invoice-to-GRN matching lifecycle.

## Implementation implications (design only)
1. Do not bolt invoice duplicate logic onto receipt_no; supplier invoice identity is a separate key.
2. Future invoice uniqueness should be enforced in the database as well as service validation, after the owner approves normalization rules and draft duplicate behavior.
3. Credit-note uniqueness and invoice/credit-note cross-reference rules need equivalent controls.
4. Introduce structured tax evidence and approved tax eligibility before using Input GST in accounting.
5. Decide currency/exchange-rate policy before supporting foreign-currency supplier invoices.
6. Keep GRN stock receipt and supplier invoice/payable lifecycle distinct, with explicit partial/multi-GRN matching and variance approvals.
7. Do not create/post journals until fiscal periods, COA mappings, tax treatment and accrual method are approved.

## Result
This audit confirms a missing supplier-invoice duplicate key and missing independent invoice lifecycle in the current purchasing schema. The live GRN table is empty, so operational duplicate behavior cannot be exercised. No implementation or database mutation was performed.

## Additional POST-route request controls
The GRN DRAFT save endpoint was inspected directly:
- Requires purchasing.create.
- Accepts only application/x-www-form-urlencoded.
- Rejects bodies larger than 65,536 bytes and parser input above 120 fields.
- Requires matching are_erp_csrf cookie and csrf_token form value using constant-time comparison.
- It then calls the DRAFT creation service; normal save does not approve or post the receipt.

The inspected purchasing route set exposes GRN create/save, approve and post actions, plus purchase-return actions. No independent supplier-invoice create/approve/post route was found in the inspected route set.