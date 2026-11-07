"""Company-scoped Purchasing queries and controlled Goods Receipt workflows."""

from datetime import date

from .db import get_connection
from .audit_service import write_audit_log
from .configuration_runtime_service import (
    resolve_purchase_line_configuration_snapshots,
    insert_purchase_configuration_snapshot,
)


PURCHASING_SECTIONS = {
    "suppliers": {
        "label": "Suppliers",
        "columns": [
            ("party_code", "Supplier Code"),
            ("party_name", "Supplier Name"),
            ("phone", "Phone"),
            ("email", "Email"),
            ("is_active", "Active"),
        ],
        "from_where": """
            FROM master.parties p
            WHERE p.company_id = %(company_id)s
              AND UPPER(p.party_type) = 'SUPPLIER'
              AND (
                %(search)s = ''
                OR p.party_code ILIKE %(pattern)s
                OR p.party_name ILIKE %(pattern)s
                OR COALESCE(p.phone, '') ILIKE %(pattern)s
                OR COALESCE(p.email, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT p.party_code, p.party_name, p.phone, p.email, p.is_active
        """,
        "order": "ORDER BY p.party_name, p.party_code",
    },
    "requisitions": {
        "label": "Requisitions",
        "columns": [
            ("requisition_no", "Requisition No."),
            ("requisition_date", "Date"),
            ("priority", "Priority"),
            ("status", "Status"),
            ("required_date", "Required Date"),
            ("line_count", "Lines"),
            ("requested_quantity", "Requested Qty"),
        ],
        "from_where": """
            FROM purchasing.purchase_requisitions r
            LEFT JOIN (
                SELECT purchase_requisition_id,
                       COUNT(*) AS line_count,
                       SUM(requested_quantity) AS requested_quantity
                FROM purchasing.purchase_requisition_lines
                GROUP BY purchase_requisition_id
            ) l ON l.purchase_requisition_id = r.id
            WHERE r.company_id = %(company_id)s
              AND (
                %(search)s = ''
                OR r.requisition_no ILIKE %(pattern)s
                OR r.status ILIKE %(pattern)s
                OR r.priority ILIKE %(pattern)s
                OR COALESCE(r.purpose, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT r.requisition_no, r.requisition_date, r.priority,
                   r.status, r.required_date,
                   COALESCE(l.line_count, 0) AS line_count,
                   COALESCE(l.requested_quantity, 0) AS requested_quantity
        """,
        "order": "ORDER BY r.requisition_date DESC, r.id DESC",
    },
    "orders": {
        "label": "Purchase Orders",
        "columns": [
            ("po_no", "PO No."),
            ("po_date", "Date"),
            ("party_name", "Supplier"),
            ("status", "Status"),
            ("expected_date", "Expected Date"),
            ("currency_code", "Currency"),
            ("grand_total", "Grand Total"),
            ("line_count", "Lines"),
        ],
        "from_where": """
            FROM purchasing.purchase_orders o
            JOIN master.parties p ON p.id = o.supplier_id
            LEFT JOIN (
                SELECT purchase_order_id, COUNT(*) AS line_count
                FROM purchasing.purchase_order_lines
                GROUP BY purchase_order_id
            ) l ON l.purchase_order_id = o.id
            WHERE o.company_id = %(company_id)s
              AND p.company_id = o.company_id
              AND (
                %(search)s = ''
                OR o.po_no ILIKE %(pattern)s
                OR o.status ILIKE %(pattern)s
                OR p.party_name ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT o.po_no, o.po_date, p.party_name, o.status,
                   o.expected_date, o.currency_code, o.grand_total,
                   COALESCE(l.line_count, 0) AS line_count
        """,
        "order": "ORDER BY o.po_date DESC, o.id DESC",
    },
    "receipts": {
        "label": "Goods Receipts",
        "columns": [
            ("receipt_no", "Receipt No."),
            ("receipt_date", "Date"),
            ("party_name", "Supplier"),
            ("po_no", "Purchase Order"),
            ("supplier_invoice_no", "Supplier Invoice"),
            ("status", "Status"),
            ("gst_choice", "GST"),
            ("grand_total", "Grand Total"),
            ("line_count", "Lines"),
        ],
        "from_where": """
            FROM purchasing.purchase_receipts r
            JOIN master.parties p ON p.id = r.supplier_id
            LEFT JOIN purchasing.purchase_orders o
                   ON o.id = r.purchase_order_id
                  AND o.company_id = r.company_id
            LEFT JOIN (
                SELECT purchase_receipt_id, COUNT(*) AS line_count
                FROM purchasing.purchase_receipt_lines
                GROUP BY purchase_receipt_id
            ) l ON l.purchase_receipt_id = r.id
            WHERE r.company_id = %(company_id)s
              AND p.company_id = r.company_id
              AND (
                %(search)s = ''
                OR r.receipt_no ILIKE %(pattern)s
                OR r.status ILIKE %(pattern)s
                OR p.party_name ILIKE %(pattern)s
                OR COALESCE(r.supplier_invoice_no, '') ILIKE %(pattern)s
                OR COALESCE(o.po_no, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT r.id, r.receipt_no, r.receipt_date, p.party_name,
                   o.po_no, r.supplier_invoice_no, r.status,
                   CASE WHEN LEFT(COALESCE(r.remarks, ''), 10) = '[GST:WITH]'
                        THEN 'With GST' ELSE 'Without GST' END AS gst_choice,
                   r.grand_total, COALESCE(l.line_count, 0) AS line_count
        """,
        "order": "ORDER BY r.receipt_date DESC, r.id DESC",
    },
    "returns": {
        "label": "Purchase Returns",
        "columns": [
            ("return_no", "Return No."),
            ("return_date", "Date"),
            ("party_name", "Supplier"),
            ("receipt_no", "Receipt No."),
            ("status", "Status"),
            ("grand_total", "Grand Total"),
            ("reason", "Reason"),
        ],
        "from_where": """
            FROM purchasing.purchase_returns r
            JOIN master.parties p ON p.id = r.supplier_id
            LEFT JOIN purchasing.purchase_receipts pr
                   ON pr.id = r.purchase_receipt_id
                  AND pr.company_id = r.company_id
            WHERE r.company_id = %(company_id)s
              AND p.company_id = r.company_id
              AND (
                %(search)s = ''
                OR r.return_no ILIKE %(pattern)s
                OR r.status ILIKE %(pattern)s
                OR p.party_name ILIKE %(pattern)s
                OR COALESCE(pr.receipt_no, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT r.id, r.return_no, r.return_date, p.party_name,
                   pr.receipt_no, r.status, r.grand_total, r.reason
        """,
        "order": "ORDER BY r.return_date DESC, r.id DESC",
    },
    "landed-costs": {
        "label": "Landed Costs",
        "columns": [
            ("landed_cost_no", "Document No."),
            ("landed_cost_date", "Date"),
            ("cost_type", "Cost Type"),
            ("party_name", "Supplier"),
            ("receipt_no", "Receipt No."),
            ("amount", "Amount"),
            ("allocation_method", "Allocation"),
            ("status", "Status"),
        ],
        "from_where": """
            FROM purchasing.purchase_landed_costs lc
            LEFT JOIN master.parties p
                   ON p.id = lc.supplier_id
                  AND p.company_id = lc.company_id
            JOIN purchasing.purchase_receipts r
                 ON r.id = lc.purchase_receipt_id
                AND r.company_id = lc.company_id
            WHERE lc.company_id = %(company_id)s
              AND (
                %(search)s = ''
                OR lc.landed_cost_no ILIKE %(pattern)s
                OR lc.cost_type ILIKE %(pattern)s
                OR lc.status ILIKE %(pattern)s
                OR r.receipt_no ILIKE %(pattern)s
                OR COALESCE(p.party_name, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT lc.landed_cost_no, lc.landed_cost_date, lc.cost_type,
                   p.party_name, r.receipt_no, lc.amount,
                   lc.allocation_method, lc.status
        """,
        "order": "ORDER BY lc.landed_cost_date DESC, lc.id DESC",
    },
    "quality": {
        "label": "Quality Inspections",
        "columns": [
            ("inspection_date", "Inspection Date"),
            ("receipt_no", "Receipt No."),
            ("party_name", "Supplier"),
            ("quality_status", "Quality Status"),
            ("inspected_quantity", "Inspected"),
            ("accepted_quantity", "Accepted"),
            ("rejected_quantity", "Rejected"),
            ("quarantine_quantity", "Quarantine"),
        ],
        "from_where": """
            FROM purchasing.receipt_quality_inspections q
            JOIN purchasing.purchase_receipts r
                 ON r.id = q.purchase_receipt_id
                AND r.company_id = q.company_id
            JOIN master.parties p
                 ON p.id = r.supplier_id
                AND p.company_id = q.company_id
            WHERE q.company_id = %(company_id)s
              AND (
                %(search)s = ''
                OR r.receipt_no ILIKE %(pattern)s
                OR p.party_name ILIKE %(pattern)s
                OR q.quality_status ILIKE %(pattern)s
                OR COALESCE(q.rejection_reason, '') ILIKE %(pattern)s
              )
        """,
        "select": """
            SELECT q.inspection_date, r.receipt_no, p.party_name,
                   q.quality_status, q.inspected_quantity,
                   q.accepted_quantity, q.rejected_quantity,
                   q.quarantine_quantity
        """,
        "order": "ORDER BY q.inspection_date DESC, q.id DESC",
    },
    "prices": {
        "label": "Supplier Item Prices",
        "columns": [
            ("party_name", "Supplier"),
            ("item_code", "Item Code"),
            ("item_name", "Item"),
            ("variant_code", "Variant"),
            ("unit_code", "Unit"),
            ("unit_price", "Unit Price"),
            ("currency_code", "Currency"),
            ("minimum_quantity", "Minimum Qty"),
            ("effective_from", "Effective From"),
            ("effective_to", "Effective To"),
            ("is_preferred", "Preferred"),
            ("is_active", "Active"),
        ],
        "from_where": """
            FROM purchasing.supplier_item_prices sp
            JOIN master.parties p
                 ON p.id = sp.supplier_id
                AND p.company_id = %(company_id)s
            JOIN master.item_variants v ON v.id = sp.item_variant_id
            JOIN master.items i ON i.id = v.item_id
            JOIN master.units u ON u.id = sp.unit_id
            WHERE (
                %(search)s = ''
                OR p.party_name ILIKE %(pattern)s
                OR i.item_code ILIKE %(pattern)s
                OR i.item_name ILIKE %(pattern)s
                OR v.variant_code ILIKE %(pattern)s
                OR COALESCE(sp.supplier_item_code, '') ILIKE %(pattern)s
            )
        """,
        "select": """
            SELECT p.party_name, i.item_code, i.item_name,
                   v.variant_code, u.code AS unit_code,
                   sp.unit_price, sp.currency_code,
                   sp.minimum_quantity, sp.effective_from,
                   sp.effective_to, sp.is_preferred, sp.is_active
        """,
        "order": "ORDER BY p.party_name, i.item_name, v.variant_code",
    },
}


def get_purchasing_page(
    company_id: int,
    section: str = "suppliers",
    search: str = "",
    page: int = 1,
    page_size: int = 25,
) -> dict:
    """Return one company-scoped Purchasing listing without database writes."""
    if section not in PURCHASING_SECTIONS:
        section = "suppliers"

    try:
        page = max(1, int(page))
    except (TypeError, ValueError):
        page = 1

    page_size = max(1, min(int(page_size), 100))
    search = str(search or "").strip()[:100]
    spec = PURCHASING_SECTIONS[section]

    params = {
        "company_id": int(company_id),
        "search": search,
        "pattern": f"%{search}%",
    }

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS total " + spec["from_where"],
                params,
            )
            total = int(cur.fetchone()["total"])
            pages = max(1, (total + page_size - 1) // page_size)
            page = min(page, pages)
            offset = (page - 1) * page_size

            sql = (
                spec["select"]
                + spec["from_where"]
                + " "
                + spec["order"]
                + " LIMIT %(limit)s OFFSET %(offset)s"
            )
            cur.execute(
                sql,
                {**params, "limit": page_size, "offset": offset},
            )
            rows = [dict(row) for row in cur.fetchall()]

    return {
        "section": section,
        "label": spec["label"],
        "sections": [
            {"key": key, "label": value["label"]}
            for key, value in PURCHASING_SECTIONS.items()
        ],
        "columns": [
            {"key": key, "label": label}
            for key, label in spec["columns"]
        ],
        "rows": rows,
        "search": search,
        "page": page,
        "pages": pages,
        "total": total,
        "page_size": page_size,
    }

def supplier_code_exists(company_id: int, supplier_code: str) -> bool:
    """Check whether a party code already exists in this company."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM master.parties
                    WHERE company_id = %s
                      AND party_code = %s
                ) AS code_exists
                """,
                (int(company_id), str(supplier_code).strip()),
            )
            return bool(cur.fetchone()["code_exists"])



def get_purchase_receipt_form_data(company_id: int) -> dict:
    """Load active master data for a draft goods-receipt form; performs SELECTs only."""
    company_id = int(company_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, party_code, party_name
                FROM master.parties
                WHERE company_id = %s
                  AND UPPER(party_type) = 'SUPPLIER'
                  AND is_active = TRUE
                ORDER BY party_name, party_code
                """,
                (company_id,),
            )
            suppliers = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT v.id AS item_variant_id,
                       i.item_code,
                       i.item_name,
                       v.variant_code,
                       v.variant_name,
                       COALESCE(v.default_unit_id, i.base_unit_id) AS default_unit_id
                FROM master.item_variants v
                JOIN master.items i ON i.id = v.item_id
                WHERE i.company_id = %s
                  AND i.is_active = TRUE
                  AND v.is_active = TRUE
                  AND i.is_stock_item = TRUE
                ORDER BY i.item_name, v.variant_code
                """,
                (company_id,),
            )
            items = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, code, name, decimal_places
                FROM master.units
                WHERE is_active = TRUE
                ORDER BY name, code
                """
            )
            units = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, code, name
                FROM master.ownership_types
                WHERE is_active = TRUE
                  AND id IN (1, 2)
                ORDER BY id
                """
            )
            ownership_types = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT id, party_code, party_name
                FROM master.parties
                WHERE company_id = %s AND is_active = TRUE
                ORDER BY party_name, party_code
                """,
                (company_id,),
            )
            parties = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT o.id, o.po_no, o.supplier_id, p.party_name
                FROM purchasing.purchase_orders o
                JOIN master.parties p
                  ON p.id = o.supplier_id AND p.company_id = o.company_id
                WHERE o.company_id = %s
                  AND o.status = 'APPROVED'
                ORDER BY o.po_date DESC, o.id DESC
                """,
                (company_id,),
            )
            purchase_orders = [dict(row) for row in cur.fetchall()]

            cur.execute(
                """
                SELECT pol.id AS purchase_order_line_id,
                       pol.purchase_order_id,
                       pol.item_variant_id,
                       pol.unit_id,
                       pol.ordered_quantity,
                       pol.received_quantity,
                       pol.unit_price,
                       i.item_name,
                       v.variant_code
                FROM purchasing.purchase_order_lines pol
                JOIN purchasing.purchase_orders po
                  ON po.id = pol.purchase_order_id AND po.company_id = %s
                JOIN master.item_variants v ON v.id = pol.item_variant_id
                JOIN master.items i ON i.id = v.item_id
                WHERE po.status = 'APPROVED'
                ORDER BY pol.purchase_order_id, pol.line_no
                """,
                (company_id,),
            )
            purchase_order_lines = [dict(row) for row in cur.fetchall()]

    return {
        "suppliers": suppliers,
        "items": items,
        "units": units,
        "ownership_types": ownership_types,
        "parties": parties,
        "purchase_orders": purchase_orders,
        "purchase_order_lines": purchase_order_lines,
    }


def _normalize_supplier_invoice_no(invoice_no) -> str | None:
    """Normalize supplier invoice identity for duplicate checks."""
    normalized = " ".join(str(invoice_no or "").strip().upper().split())
    return normalized or None


def _require_single_raw_store_location(locations) -> int:
    """Return the one valid company RAW_STORE inventory-location ID."""
    if len(locations) != 1:
        raise ValueError(
            "The company must have exactly one active stock-enabled RAW_STORE "
            "location before a Goods Receipt can be saved."
        )
    return int(locations[0]["id"])


def create_purchase_receipt_draft(
    company_id: int,
    created_by: int,
    user,
    request,
    header: dict,
    lines: list[dict],
) -> dict:
    """Persist a Goods Receipt as DRAFT only. Never approves or posts stock."""
    from decimal import Decimal, InvalidOperation

    company_id = int(company_id)
    created_by = int(created_by)
    if not lines:
        raise ValueError("Add at least one purchase line.")
    if len(lines) > 10:
        raise ValueError("A Goods Receipt can contain no more than 10 item lines.")

    def amount(value, label, places, integer_limit=None):
        try:
            result = Decimal(str(value or "0").strip())
        except (InvalidOperation, ValueError):
            raise ValueError(f"{label} must be a valid number.")
        if not result.is_finite() or result < 0:
            raise ValueError(f"{label} must be a non-negative number.")
        normalized = result.normalize()
        fraction = max(0, -normalized.as_tuple().exponent)
        integer = max(0, normalized.adjusted() + 1) if result else 0
        allowed_integer = (20 - places) if integer_limit is None else integer_limit
        if fraction > places or integer > allowed_integer:
            raise ValueError(f"{label} exceeds the allowed numeric precision.")
        return result

    try:
        supplier_id = int(header.get("supplier_id") or 0)
        po_id = int(header.get("purchase_order_id") or 0) or None
    except (TypeError, ValueError):
        raise ValueError("Select a valid supplier and purchase order.")
    gst_choice = str(header.get("gst_choice") or "WITHOUT").upper()
    if gst_choice not in {"WITH", "WITHOUT"}:
        raise ValueError("Choose With GST or Without GST.")

    prepared = []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    for index, raw in enumerate(lines, start=1):
        try:
            variant_id = int(raw.get("item_variant_id") or 0)
            unit_id = int(raw.get("unit_id") or 0)
            ownership_id = int(raw.get("ownership_type_id") or 0)
            owner_party_id = int(raw.get("owner_party_id") or 0) or None
            po_line_id = int(raw.get("purchase_order_line_id") or 0) or None
        except (TypeError, ValueError):
            raise ValueError(f"Line {index}: select a valid item, unit and ownership.")
        quantity = amount(raw.get("received_quantity"), f"Line {index} quantity", 3, 15)
        unit_price = amount(raw.get("unit_price"), f"Line {index} rate", 6, 12)
        discount = amount(raw.get("discount_amount"), f"Line {index} discount", 6)
        tax = amount(raw.get("tax_amount"), f"Line {index} GST amount", 6)
        if quantity <= 0:
            raise ValueError(f"Line {index}: quantity must be greater than zero.")
        if gst_choice == "WITHOUT" and tax != 0:
            raise ValueError("GST amount must be zero when Without GST is selected.")
        if ownership_id != 1 or owner_party_id is not None:
            raise ValueError(
                "Supplier Goods Receipts accept OWN stock only. "
                "Use the separate Party Stock Receipt workflow for PARTY-owned material."
            )
        if len(str(raw.get("remarks") or "")) > 500:
            raise ValueError(f"Line {index}: remarks cannot exceed 500 characters.")
        base = quantity * unit_price
        if discount > base:
            raise ValueError(f"Line {index}: discount cannot exceed line value.")
        line_total = base - discount + tax
        subtotal += base
        discount_total += discount
        tax_total += tax
        prepared.append({
            "line_no": index,
            "item_variant_id": variant_id,
            "unit_id": unit_id,
            "received_quantity": quantity,
            "unit_price": unit_price,
            "discount_amount": discount,
            "tax_amount": tax,
            "line_total": line_total,
            "ownership_type_id": ownership_id,
            "owner_party_id": owner_party_id,
            "purchase_order_line_id": po_line_id,
            "remarks": str(raw.get("remarks") or "").strip() or None,
        })

    freight = amount(header.get("freight_amount"), "Freight", 6)
    other = amount(header.get("other_charges"), "Other charges", 6)
    header_discount = amount(header.get("discount_amount"), "Header discount", 6)
    if header_discount > subtotal - discount_total:
        raise ValueError("Header discount cannot exceed the remaining subtotal.")
    grand_total = subtotal - discount_total - header_discount + tax_total + freight + other
    if len(str(header.get("supplier_invoice_no") or "")) > 100:
        raise ValueError("Supplier invoice number cannot exceed 100 characters.")
    if len(str(header.get("remarks") or "")) > 4000:
        raise ValueError("Remarks cannot exceed 4,000 characters.")

    receipt_date = str(header.get("receipt_date") or "").strip() or None
    effective_on = date.fromisoformat(receipt_date) if receipt_date else date.today()
    invoice_date = str(header.get("supplier_invoice_date") or "").strip() or None
    supplier_invoice_no = _normalize_supplier_invoice_no(header.get("supplier_invoice_no"))
    user_remarks = str(header.get("remarks") or "").strip()
    # The existing receipt table has no GST-choice column. Preserve the explicit choice
    # in the header remarks without inventing a tax rate or altering the schema.
    remarks = f"[GST:{gst_choice}]" + (f"\n{user_remarks}" if user_remarks else "")

    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM master.parties
                WHERE id = %s AND company_id = %s
                  AND UPPER(party_type) = 'SUPPLIER' AND is_active = TRUE
                """,
                (supplier_id, company_id),
            )
            if cur.fetchone() is None:
                raise ValueError("Select an active supplier belonging to this company.")

            if supplier_invoice_no:
                # Serialize duplicate checks for this company/supplier/invoice key.
                # The advisory lock avoids concurrent draft saves racing each other.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"supplier_invoice:{company_id}:{supplier_id}:{supplier_invoice_no}",),
                )
                cur.execute(
                    """
                    SELECT receipt_no, status
                    FROM purchasing.purchase_receipts
                    WHERE company_id = %s AND supplier_id = %s
                      AND UPPER(REGEXP_REPLACE(BTRIM(supplier_invoice_no), '[[:space:]]+', ' ', 'g')) = %s
                    ORDER BY id
                    LIMIT 1
                    FOR SHARE
                    """,
                    (company_id, supplier_id, supplier_invoice_no),
                )
                duplicate_invoice = cur.fetchone()
                if duplicate_invoice is not None:
                    raise ValueError(
                        f"Supplier invoice {supplier_invoice_no} is already recorded "
                        f"on Goods Receipt {duplicate_invoice['receipt_no']} "
                        f"({duplicate_invoice['status']}). Duplicate invoice entry is blocked."
                    )

            if po_id:
                cur.execute(
                    """
                    SELECT supplier_id FROM purchasing.purchase_orders
                    WHERE id = %s AND company_id = %s AND status = 'APPROVED'
                    FOR SHARE
                    """,
                    (po_id, company_id),
                )
                po = cur.fetchone()
                if po is None or int(po["supplier_id"]) != supplier_id:
                    raise ValueError("The selected approved Purchase Order does not belong to this supplier.")

            po_line_totals = {}
            for line in prepared:
                po_line_id = line["purchase_order_line_id"]
                if po_line_id:
                    po_line_totals[po_line_id] = (
                        po_line_totals.get(po_line_id, Decimal("0"))
                        + line["received_quantity"]
                    )

            for line in prepared:
                cur.execute(
                    """
                    SELECT 1
                    FROM master.item_variants v
                    JOIN master.items i ON i.id = v.item_id
                    WHERE v.id = %s AND v.is_active = TRUE
                      AND i.company_id = %s AND i.is_active = TRUE
                      AND i.is_stock_item = TRUE
                      AND COALESCE(v.default_unit_id, i.base_unit_id) = %s
                    """,
                    (line["item_variant_id"], company_id, line["unit_id"]),
                )
                if cur.fetchone() is None:
                    raise ValueError(f"Line {line['line_no']}: item variant is inactive or outside this company.")
                cur.execute("SELECT 1 FROM master.units WHERE id = %s AND is_active = TRUE", (line["unit_id"],))
                if cur.fetchone() is None:
                    raise ValueError(f"Line {line['line_no']}: select an active unit.")
                cur.execute("SELECT 1 FROM master.ownership_types WHERE id = %s AND is_active = TRUE", (line["ownership_type_id"],))
                if cur.fetchone() is None:
                    raise ValueError(f"Line {line['line_no']}: ownership type is not active.")
                if line["owner_party_id"] is not None:
                    cur.execute(
                        "SELECT 1 FROM master.parties WHERE id = %s AND company_id = %s AND is_active = TRUE",
                        (line["owner_party_id"], company_id),
                    )
                    if cur.fetchone() is None:
                        raise ValueError(f"Line {line['line_no']}: owner party is invalid for this company.")

                cur.execute(
                    """SELECT i.id,i.item_code,i.item_name,
                              u.id AS unit_id,u.code,u.name,u.decimal_places
                       FROM master.item_variants v
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.units u ON u.id=%s
                       WHERE v.id=%s AND i.company_id=%s
                         AND i.is_active AND v.is_active AND u.is_active
                       FOR SHARE OF i,v,u""",
                    (line["unit_id"], line["item_variant_id"], company_id),
                )
                identity = cur.fetchone()
                if identity is None:
                    raise ValueError(f"Line {line['line_no']}: item/unit master identity is no longer active.")
                identity = dict(identity)
                item_master = {
                    "id": identity["id"],
                    "item_code": identity["item_code"],
                    "item_name": identity["item_name"],
                }
                unit_master = {
                    "id": identity["unit_id"],
                    "code": identity["code"],
                    "name": identity["name"],
                    "decimal_places": identity["decimal_places"],
                }
                line["configuration_snapshots"] = resolve_purchase_line_configuration_snapshots(
                    cur, company_id=company_id, effective_on=effective_on,
                    item_master=item_master, unit_master=unit_master,
                )

                po_line_id = line["purchase_order_line_id"]
                if po_line_id:
                    if not po_id:
                        raise ValueError("A PO line cannot be selected for a Direct Purchase without a PO.")
                    cur.execute(
                        """
                        SELECT ordered_quantity, received_quantity
                        FROM purchasing.purchase_order_lines
                        WHERE id = %s AND purchase_order_id = %s
                          AND item_variant_id = %s AND unit_id = %s
                        FOR SHARE
                        """,
                        (po_line_id, po_id, line["item_variant_id"], line["unit_id"]),
                    )
                    po_line = cur.fetchone()
                    if po_line is None:
                        raise ValueError(f"Line {line['line_no']}: selected PO line does not match this item and order.")
                    remaining = Decimal(str(po_line["ordered_quantity"])) - Decimal(str(po_line["received_quantity"]))
                    if po_line_totals[po_line_id] > remaining:
                        raise ValueError(
                            f"Line {line['line_no']}: combined received quantity "
                            f"for this PO line exceeds the remaining approved "
                            f"quantity ({remaining})."
                        )
                elif po_id:
                    raise ValueError(f"Line {line['line_no']}: select the matching Purchase Order line.")

            # Resolve the company's single raw-material godown by its stable
            # master code; never depend on a seeded numeric inventory-location ID.
            cur.execute(
                """
                SELECT il.id
                FROM inventory.locations il
                JOIN core.locations cl ON cl.id = il.core_location_id
                WHERE cl.company_id = %s
                  AND cl.code = 'RAW_STORE'
                  AND cl.is_active = TRUE
                  AND il.is_active = TRUE
                  AND il.allow_stock = TRUE
                FOR SHARE OF il, cl
                """,
                (company_id,),
            )
            raw_store_locations = cur.fetchall()
            warehouse_location_id = _require_single_raw_store_location(
                raw_store_locations
            )

            cur.execute(
                "SELECT core.get_next_document_no(%s, %s) AS document_no",
                (company_id, "PURCHASE_RECEIPT"),
            )
            receipt_no = cur.fetchone()["document_no"]
            cur.execute(
                """
                INSERT INTO purchasing.purchase_receipts (
                    company_id, receipt_no, receipt_date, purchase_order_id,
                    supplier_id, supplier_invoice_no, supplier_invoice_date,
                    status, warehouse_location_id, subtotal, discount_amount,
                    tax_amount, freight_amount, other_charges, grand_total,
                    remarks, created_by
                ) VALUES (
                    %s, %s, COALESCE(%s::date, CURRENT_DATE), %s,
                    %s, %s, %s::date, 'DRAFT', %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                ) RETURNING id
                """,
                (
                    company_id, receipt_no, receipt_date, po_id, supplier_id,
                    str(header.get("supplier_invoice_no") or "").strip() or None,
                    invoice_date, warehouse_location_id, subtotal,
                    discount_total + header_discount, tax_total, freight, other,
                    grand_total, remarks, created_by,
                ),
            )
            receipt_id = int(cur.fetchone()["id"])

            for line in prepared:
                cur.execute(
                    """
                    INSERT INTO purchasing.purchase_receipt_lines (
                        purchase_receipt_id, line_no, purchase_order_line_id,
                        item_variant_id, received_quantity, unit_id, unit_price,
                        discount_amount, tax_amount, freight_amount, other_charges,
                        line_total, ownership_type_id, owner_party_id, remarks
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        receipt_id, line["line_no"], line["purchase_order_line_id"],
                        line["item_variant_id"], line["received_quantity"],
                        line["unit_id"], line["unit_price"], line["discount_amount"],
                        line["tax_amount"], line["line_total"],
                        line["ownership_type_id"], line["owner_party_id"],
                        line["remarks"],
                    ),
                )
                receipt_line_id = int(cur.fetchone()["id"])
                for snapshot in line["configuration_snapshots"]:
                    insert_purchase_configuration_snapshot(
                        cur, company_id=company_id, receipt_id=receipt_id,
                        receipt_line_id=receipt_line_id, user_id=created_by,
                        snapshot=snapshot,
                    )

        write_audit_log(
            conn,
            user=user,
            request=request,
            action="CREATE",
            table_name="purchasing.purchase_receipts",
            record_id=receipt_id,
            document_no=receipt_no,
            new_values={
                "receipt_no": receipt_no,
                "status": "DRAFT",
                "supplier_id": supplier_id,
                "purchase_order_id": po_id,
                "receipt_date": receipt_date,
                "supplier_invoice_no": (
                    str(header.get("supplier_invoice_no") or "").strip() or None
                ),
                "subtotal": subtotal,
                "discount_total": discount_total,
                "header_discount": header_discount,
                "tax_total": tax_total,
                "freight_amount": freight,
                "other_charges": other,
                "grand_total": grand_total,
                "line_count": len(prepared),
                "lines": [
                    {
                        "line_no": line["line_no"],
                        "item_variant_id": line["item_variant_id"],
                        "purchase_order_line_id": line["purchase_order_line_id"],
                        "received_quantity": line["received_quantity"],
                        "unit_id": line["unit_id"],
                        "unit_price": line["unit_price"],
                        "discount_amount": line["discount_amount"],
                        "tax_amount": line["tax_amount"],
                        "line_total": line["line_total"],
                        "ownership_type_id": line["ownership_type_id"],
                        "owner_party_id": line["owner_party_id"],
                        "configuration_snapshots": [
                            {
                                "config_type": snapshot["config_type"],
                                "config_key": snapshot["config_key"],
                                "source": snapshot["source"],
                                "configuration_version_id": snapshot["configuration_version_id"],
                                "payload": snapshot["payload"],
                            }
                            for snapshot in line["configuration_snapshots"]
                        ],
                    }
                    for line in prepared
                ],
            },
            reason="Goods Receipt DRAFT creation",
            module="PURCHASING",
        )

    return {"id": receipt_id, "receipt_no": receipt_no, "status": "DRAFT"}



def _allocate_receipt_amount(total, weights, *, label):
    """Allocate a header amount by line value, preserving the exact 6dp total."""
    from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

    quantum = Decimal("0.000001")
    total = Decimal(str(total or 0)).quantize(quantum, rounding=ROUND_HALF_UP)
    weight_total = sum(weights, Decimal("0"))
    if total == 0:
        return [Decimal("0.000000") for _ in weights]
    if weight_total <= 0:
        raise ValueError(
            f"Cannot allocate {label}: the net item value is zero. "
            "Correct the discounts or remove the additional charge."
        )
    allocations = []
    allocated = Decimal("0")
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            part = total - allocated
        else:
            part = (total * weight / weight_total).quantize(
                quantum, rounding=ROUND_DOWN
            )
            allocated += part
        if part < 0:
            raise ValueError(f"{label} allocation cannot be negative.")
        allocations.append(part)
    return allocations


def approve_purchase_receipt(
    company_id: int,
    receipt_id: int,
    approved_by: int,
    user,
    request,
) -> dict:
    """Approve a supplier GRN and create its one approved inward stock document.

    A transaction-scoped advisory lock serializes all app-level actions for a GRN;
    the existing generic stock-document reference fields provide the durable link.
    """
    from decimal import Decimal, ROUND_HALF_UP

    company_id = int(company_id)
    receipt_id = int(receipt_id)
    approved_by = int(approved_by)
    quantum = Decimal("0.000001")

    with get_connection() as conn, conn.transaction():
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"purchase_receipt:{company_id}:{receipt_id}",),
            )
            cur.execute(
                """
                SELECT id, receipt_no, receipt_date, purchase_order_id,
                       supplier_id, status, warehouse_location_id,
                       discount_amount, freight_amount, other_charges, remarks
                FROM purchasing.purchase_receipts
                WHERE id = %s AND company_id = %s
                FOR UPDATE
                """,
                (receipt_id, company_id),
            )
            receipt = cur.fetchone()
            if receipt is None:
                raise ValueError("Goods Receipt was not found for this company.")

            cur.execute(