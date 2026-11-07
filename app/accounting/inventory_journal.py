"""Controlled bridge from a POSTED stock document to a GL DRAFT.

This module deliberately does not invent debit/credit policy or account mappings.
A caller must provide fully prepared journal lines under an approved mapping.
The caller owns one database transaction for both source validation and journal
creation; this function never commits or posts a journal.
"""
from .journal_service import create_journal_draft
from .journal_rules import validate_journal_lines


SUPPORTED_STOCK_DOCUMENT_TYPES = frozenset({
    "PURCHASE_RECEIPT",
    "PURCHASE_RETURN",
    "PRODUCTION_CONSUMPTION",
    "PRODUCTION_OUTPUT",
    "STOCK_TRANSFER",
    "STOCK_ADJUSTMENT",
    "STOCK_OPENING",
    "STOCK_RECLASSIFICATION",
    "SALES_DISPATCH",
})


def create_stock_document_journal_draft(
    conn, *, company_id, stock_document_id, user, request, journal_lines,
    description=None,
):
    """Create one source-linked GL DRAFT for a POSTED, company-owned stock doc.

    PARTY-owned lines are rejected rather than capitalized as ARE inventory.
    Account selection, debit/credit direction and amounts must be supplied by
    the caller; existing journal validation checks balance and account/party
    references. Fiscal period and source idempotency are enforced downstream.
    """
    company_id = int(company_id)
    stock_document_id = int(stock_document_id)
    if company_id <= 0 or stock_document_id <= 0:
        raise ValueError("Company and stock document IDs must be positive.")

    basis = get_stock_document_journal_basis(
        conn, company_id=company_id, stock_document_id=stock_document_id
    )
    if not basis["ready_for_mapping_review"]:
        raise ValueError(
            "Stock document valuation basis is not ready: "
            + "; ".join(basis["blockers"])
        )
    if basis["document_type"] == "STOCK_OPENING":
        raise ValueError(
            "STOCK_OPENING requires an approved opening-stock clearing account "
            "and opening valuation policy before a GL DRAFT can be created."
        )
    validated_lines = validate_journal_lines(journal_lines)
    expected_value = basis["gross_movement_value"]
    if validated_lines["debit_total"] != expected_value:
        raise ValueError(
            "Journal amount does not match the stock document valuation basis "
            f"({expected_value}). No GL DRAFT was created."
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, company_id, document_no, document_type,
                   document_date, status
            FROM inventory.stock_documents
            WHERE id = %s AND company_id = %s
            FOR SHARE
            """,
            (stock_document_id, company_id),
        )
        document = cur.fetchone()
        if not document:
            raise ValueError("Stock document was not found for this company.")
        if str(document["status"]).upper() != "POSTED":
            raise ValueError("Only a POSTED stock document can create a GL DRAFT.")
        if not document["document_date"] or not document["document_type"]:
            raise ValueError("Stock document date/type is missing; GL DRAFT is blocked.")

        cur.execute(
            """
            SELECT ownership_type_id, owner_party_id
            FROM inventory.stock_document_lines
            WHERE stock_document_id = %s
            ORDER BY id
            FOR SHARE
            """,
            (stock_document_id,),
        )
        stock_lines = cur.fetchall()
        if not stock_lines:
            raise ValueError("Stock document has no lines; GL DRAFT is blocked.")

    party_lines = [
        row for row in stock_lines
        if int(row["ownership_type_id"] or 0) != 1
        or row["owner_party_id"] is not None
    ]
    if party_lines:
        raise ValueError(
            "Stock document contains PARTY-owned lines. Split and reconcile "
            "OWN/PARTY stock before creating an ARE inventory journal."
        )

    source_type = str(document["document_type"]).strip().upper()
    if not source_type:
        raise ValueError("Stock document type is invalid.")

    return create_journal_draft(
        conn,
        company_id=company_id,
        user=user,
        request=request,
        entry_date=document["document_date"],
        description=(
            description
            or f"Inventory {source_type}: {document['document_no']}"
        ),
        lines=journal_lines,
        source_module="INVENTORY",
        source_type="STOCK_DOCUMENT",
        source_id=stock_document_id,
    )


def get_stock_document_journal_basis(conn, *, company_id, stock_document_id):
    """Read a valuation basis for mapping review; never creates or posts a journal.

    Values are grouped by the actual master item-category code. Missing or
    invalid costs/categories are returned as blockers, not silently guessed.
    Transfers are reported separately because same-godown movements are not
    automatically P&L or inventory-value changes.
    """
    from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

    company_id = int(company_id)
    stock_document_id = int(stock_document_id)
    if company_id <= 0 or stock_document_id <= 0:
        raise ValueError("Company and stock document IDs must be positive.")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, document_no, document_type, document_date, status
            FROM inventory.stock_documents
            WHERE id = %s AND company_id = %s
            """,
            (stock_document_id, company_id),
        )
        document = cur.fetchone()
        if not document:
            raise ValueError("Stock document was not found for this company.")
        if str(document["status"]).upper() != "POSTED":
            raise ValueError("Only a POSTED stock document has a journal valuation basis.")

        cur.execute(
            """
            SELECT sdl.id AS line_id, sdl.quantity_in, sdl.quantity_out,
                   sdl.unit_cost, sdl.total_cost,
                   sdl.ownership_type_id, sdl.owner_party_id,
                   ic.code AS category_code, ic.name AS category_name
            FROM inventory.stock_document_lines sdl
            JOIN master.item_variants v ON v.id = sdl.item_variant_id
            JOIN master.items i ON i.id = v.item_id
            LEFT JOIN master.item_categories ic
              ON ic.id = i.item_category_id AND ic.company_id = %s
            WHERE sdl.stock_document_id = %s
            ORDER BY sdl.id
            """,
            (company_id, stock_document_id),
        )
        rows = cur.fetchall()

    if not rows:
        raise ValueError("Stock document has no lines; valuation basis is unavailable.")

    blockers = []
    grouped = {}
    total_in = Decimal("0")
    total_out = Decimal("0")
    has_party = False

    for row in rows:
        line_id = int(row["line_id"])
        if int(row["ownership_type_id"] or 0) != 1 or row["owner_party_id"] is not None:
            has_party = True
            blockers.append(f"Line {line_id}: PARTY-owned stock is excluded from ARE inventory.")
            continue

        category_code = str(row["category_code"] or "").strip().upper()
        category_name = str(row["category_name"] or "").strip()
        if not category_code:
            blockers.append(f"Line {line_id}: item category/account mapping key is missing.")
            continue

        try:
            qty_in = Decimal(str(row["quantity_in"] or 0))
            qty_out = Decimal(str(row["quantity_out"] or 0))
            unit_cost = (
                Decimal(str(row["unit_cost"]))
                if row["unit_cost"] is not None else None
            )
            total_cost = (
                Decimal(str(row["total_cost"]))
                if row["total_cost"] is not None else None
            )
        except (InvalidOperation, TypeError, ValueError):
            blockers.append(f"Line {line_id}: quantity or cost is not numeric.")
            continue

        if not qty_in.is_finite() or not qty_out.is_finite() or qty_in < 0 or qty_out < 0:
            blockers.append(f"Line {line_id}: invalid stock movement quantity.")
            continue
        if qty_in > 0 and qty_out > 0:
            blockers.append(f"Line {line_id}: simultaneous inward and outward quantity needs review.")
            continue
        quantity = qty_in if qty_in > 0 else qty_out
        if quantity <= 0:
            blockers.append(f"Line {line_id}: no inward or outward quantity.")
            continue

        if total_cost is not None:
            value = abs(total_cost)
        elif unit_cost is not None and unit_cost.is_finite() and unit_cost >= 0:
            value = (quantity * unit_cost).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        else:
            blockers.append(f"Line {line_id}: neither a valid total cost nor unit cost is available.")
            continue

        if not value.is_finite() or value < 0:
            blockers.append(f"Line {line_id}: invalid extended stock value.")
            continue

        bucket = grouped.setdefault(
            category_code,
            {
                "category_code": category_code,
                "category_name": category_name,
                "inward_value": Decimal("0"),
                "outward_value": Decimal("0"),
                "line_count": 0,
            },
        )
        bucket["line_count"] += 1
        if qty_in > 0:
            bucket["inward_value"] += value
            total_in += value
        else:
            bucket["outward_value"] += value
            total_out += value

    document_type = str(document["document_type"] or "").strip().upper()
    is_transfer = document_type == "STOCK_TRANSFER"
    if document_type not in SUPPORTED_STOCK_DOCUMENT_TYPES:
        blockers.append(
            f"Unsupported stock document type {document_type or '(blank)'}; "
            "no GL journal may be created."
        )
    if has_party:
        blockers.append("Split OWN and PARTY stock before any ARE inventory journal.")
    if is_transfer:
        blockers.append(
            "STOCK_TRANSFER is a location movement; no automatic GL journal is proposed."
        )

    return {
        "document_id": stock_document_id,
        "document_no": document["document_no"],
        "document_type": document_type,
        "document_date": document["document_date"],
        "status": "POSTED",
        "categories": sorted(grouped.values(), key=lambda item: item["category_code"]),
        "total_inward_value": total_in,
        "total_outward_value": total_out,
        "net_stock_value_change": total_in - total_out,
        "gross_movement_value": total_in + total_out,
        "line_count": len(rows),
        "ready_for_mapping_review": not blockers and not is_transfer,
        "automatic_journal_approved": False,
        "blockers": blockers,
    }