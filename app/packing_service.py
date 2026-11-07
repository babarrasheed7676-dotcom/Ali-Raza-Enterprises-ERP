"""Draft-only packing workflow. This phase never posts or reserves stock."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .db import get_connection
from .audit_service import write_audit_log
from .configuration_runtime_service import resolve_nalki_packaging_snapshot, insert_packing_configuration_snapshot

PIECES_PER_SMALL_BOX = 10
SMALL_BOXES_PER_FINISHED_BOX = 10
PIECES_PER_FINISHED_BOX = PIECES_PER_SMALL_BOX * SMALL_BOXES_PER_FINISHED_BOX
REGULAR_SMALL_BOX_VARIANT_CODE = "PACK_BOX-STD"  # Existing master variant 5421; 10-piece regular box.
ELIGIBLE_PACKING_SOURCE_STAGE_CODES = ("NALKI", "LABELING")


def normalize_packing_lines(lines: list[dict[str, Any]]) -> list[dict[str, int]]:
    if not isinstance(lines, list) or not 1 <= len(lines) <= 20:
        raise ValueError("Packing order requires 1–20 item lines.")
    normalized = []
    seen = set()
    for index, line in enumerate(lines, start=1):
        try:
            variant_id = int(str(line.get("item_variant_id", "")).strip())
            finished_boxes = int(str(line.get("finished_boxes_qty", "")).strip())
        except (TypeError, ValueError):
            raise ValueError(f"Line {index}: select a valid Nalki variant and whole finished-box quantity.")
        if variant_id <= 0 or finished_boxes <= 0:
            raise ValueError(f"Line {index}: variant and finished-box quantity must be positive.")
        if variant_id in seen:
            raise ValueError(f"Line {index}: duplicate Nalki variant; combine its quantity into one line.")
        if finished_boxes > 100000:
            raise ValueError(f"Line {index}: finished-box quantity exceeds the safe limit.")
        seen.add(variant_id)
        normalized.append({
            "item_variant_id": variant_id,
            "finished_boxes_qty": finished_boxes,
            "quantity_pieces": finished_boxes * PIECES_PER_FINISHED_BOX,
            "small_boxes_qty": finished_boxes * SMALL_BOXES_PER_FINISHED_BOX,
        })
    return normalized


def calculate_finished_box_material_requirements(finished_boxes_qty: Any) -> dict[str, int]:
    """A 100-piece finished box consumes ten separate 10-piece regular boxes."""
    count = int(str(finished_boxes_qty).strip())
    if count <= 0 or count > 100000:
        raise ValueError("Finished 100-piece box quantity must be a positive whole number.")
    return {
        "finished_100_piece_boxes": count,
        "regular_10_piece_boxes": count * SMALL_BOXES_PER_FINISHED_BOX,
        "nalki_pieces": count * PIECES_PER_FINISHED_BOX,
    }


def validate_finished_box_shade_composition(
    lines: list[dict[str, Any]], finished_boxes_qty: Any,
    expected_unique_shades: int = 100,
) -> list[dict[str, int]]:
    """One finished assortment box contains one piece of each of 100 unique shades.

    For N finished boxes, every selected shade variant must supply N pieces.
    The ten regular 10-piece boxes are a separate packaging-material consumption,
    not a per-shade box count.
    """
    try:
        box_count = int(str(finished_boxes_qty).strip())
    except (TypeError, ValueError):
        raise ValueError("Finished box quantity must be a positive whole number.")
    if box_count <= 0 or box_count > 100000:
        raise ValueError("Finished box quantity must be a positive whole number.")
    if not isinstance(lines, list) or len(lines) != expected_unique_shades:
        raise ValueError(f"Each 100-piece finished box requires exactly {expected_unique_shades} unique shades.")
    seen_variants: set[int] = set()
    seen_shades: set[int] = set()
    brand_ids: set[int] = set()
    normalized: list[dict[str, int]] = []
    for index, line in enumerate(lines, start=1):
        try:
            variant_id = int(str(line.get("item_variant_id", "")).strip())
            shade_id = int(str(line.get("shade_id", "")).strip())
            brand_id = int(str(line.get("brand_id", "")).strip())
            available = int(str(line.get("available_pieces", "")).strip())
        except (TypeError, ValueError):
            raise ValueError(f"Shade line {index}: valid Nalki variant, brand, shade and available stock are required.")
        if min(variant_id, shade_id, brand_id) <= 0 or available < 0:
            raise ValueError(f"Shade line {index}: invalid master IDs or available stock.")
        if variant_id in seen_variants or shade_id in seen_shades:
            raise ValueError("A finished assortment box must contain 100 different shades without duplicates.")
        seen_variants.add(variant_id)
        seen_shades.add(shade_id)
        brand_ids.add(brand_id)
        if available < box_count:
            raise ValueError(f"Shade line {index}: insufficient OWN stock; {available} available, {box_count} required.")
        normalized.append({
            "item_variant_id": variant_id,
            "brand_id": brand_id,
            "shade_id": shade_id,
            "quantity_pieces": box_count,
            "pieces_per_finished_box": 1,
        })
    if len(brand_ids) != 1:
        raise ValueError("All 100 shades in one finished box must belong to the same brand.")
    return normalized


def validate_packing_source_quantity(requested_pieces: Any, available_pieces: Any) -> None:
    """Require enough OWN Nalki stock in Nalki/Labeling stages for a whole-box plan."""
    requested = Decimal(str(requested_pieces))
    available = Decimal(str(available_pieces))
    if requested <= 0:
        raise ValueError("Packing quantity must be greater than zero.")
    if available < requested:
        raise ValueError(
            f"Insufficient OWN Nalki stock in Nalki/Labeling stages: "
            f"{available} pieces available; {requested} pieces required."
        )


def _packing_decimal(value: Any, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field_name} must be a valid number.")
    if not result.is_finite():
        raise ValueError(f"{field_name} must be a finite number.")
    return result


def validate_packing_material_quantities(
    issued: Any, used: Any, returned: Any, wasted: Any,
) -> dict[str, Decimal]:
    """Mirror the database's material arithmetic check before a material issue is saved."""
    values = {
        "issued": _packing_decimal(issued, "Issued quantity"),
        "used": _packing_decimal(used, "Used quantity"),
        "returned": _packing_decimal(returned, "Returned quantity"),
        "wasted": _packing_decimal(wasted, "Wasted quantity"),
    }
    if any(value < 0 for value in values.values()):
        raise ValueError("Packing material quantities cannot be negative.")
    if values["used"] + values["returned"] + values["wasted"] > values["issued"]:
        raise ValueError("Used + returned + wasted quantity cannot exceed issued quantity.")
    return values


def validate_packing_empty_box_return(
    issued_small_boxes: Any, good_returned: Any, damaged_returned: Any = 0,
) -> dict[str, Decimal]:
    """Validate empty small-box counts without assuming an unconfirmed packaging SKU."""
    values = {
        "issued": _packing_decimal(issued_small_boxes, "Small boxes issued"),
        "good_returned": _packing_decimal(good_returned, "Good empty boxes returned"),
        "damaged_returned": _packing_decimal(damaged_returned, "Damaged empty boxes returned"),
    }
    if any(value < 0 for value in values.values()):
        raise ValueError("Empty small-box quantities cannot be negative.")
    if values["good_returned"] + values["damaged_returned"] > values["issued"]:
        raise ValueError("Good + damaged empty boxes returned cannot exceed small boxes issued.")
    return values


def validate_packing_quality(
    inspected: Any, passed: Any, rejected: Any,
) -> dict[str, Any]:
    """Validate inspected/pass/reject quantities and derive a safe QC status."""
    quantities = {
        "inspected": _packing_decimal(inspected, "Inspected quantity"),
        "passed": _packing_decimal(passed, "Passed quantity"),
        "rejected": _packing_decimal(rejected, "Rejected quantity"),
    }
    if quantities["inspected"] <= 0:
        raise ValueError("Inspected quantity must be greater than zero.")
    if any(quantities[key] < 0 for key in ("passed", "rejected")):
        raise ValueError("Passed and rejected quantities cannot be negative.")
    if quantities["passed"] + quantities["rejected"] > quantities["inspected"]:
        raise ValueError("Passed + rejected quantity cannot exceed inspected quantity.")
    if quantities["passed"] == quantities["inspected"] and quantities["rejected"] == 0:
        status = "PASSED"
    elif quantities["passed"] == 0 and quantities["rejected"] > 0:
        status = "FAILED"
    else:
        status = "PARTIAL"
    return {**quantities, "status": status}


PACKING_WASTAGE_TYPES = frozenset({"NALKI", "TUBE", "PACKING_BOX", "LABEL", "PLASTIC_BAG", "CARTON", "OTHER"})


def validate_packing_wastage(wastage_type: str, quantity: Any, reason: str) -> dict[str, Any]:
    kind = str(wastage_type or "").strip().upper()
    amount = _packing_decimal(quantity, "Wastage quantity")
    detail = str(reason or "").strip()
    if kind not in PACKING_WASTAGE_TYPES:
        raise ValueError("Select a valid packing wastage type.")
    if amount <= 0:
        raise ValueError("Wastage quantity must be greater than zero.")
    if not detail:
        raise ValueError("Wastage reason is required.")
    if len(detail) > 500:
        raise ValueError("Wastage reason cannot exceed 500 characters.")
    return {"wastage_type": kind, "quantity": amount, "reason": detail}


def validate_packing_labour(boxes_qty: Any, rate_per_box: Any) -> dict[str, Decimal]:
    """Packing labour is box-based; this does not create Baby Cone salary/theka entries."""
    boxes = _packing_decimal(boxes_qty, "Packing labour boxes")
    rate = _packing_decimal(rate_per_box, "Packing labour rate per box")
    if boxes <= 0:
        raise ValueError("Packing labour box quantity must be greater than zero.")
    if rate < 0:
        raise ValueError("Packing labour rate cannot be negative.")
    return {"boxes_qty": boxes, "rate_per_box": rate, "labour_amount": boxes * rate, "labour_type": "PACKING"}


def parse_packing_date(value: str) -> date:
    try:
        result = date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Enter a valid packing date.")
    if result > date.today():
        raise ValueError("Packing date cannot be in the future.")
    return result


def get_packing_form_data(company_id: int) -> dict:
    """Return active OWN Nalki variants with current positive stock for selection."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT v.id AS item_variant_id,v.variant_code,v.variant_name,
                          b.name AS brand_name,sh.shade_code,sh.shade_name,
                          SUM(sb.quantity) AS available_quantity,
                          string_agg(DISTINCT ps.name, ', ' ORDER BY ps.name) AS process_stages
                   FROM inventory.stock_balances sb
                   JOIN inventory.locations il ON il.id=sb.location_id
                     AND il.is_active=TRUE AND il.allow_stock=TRUE
                   JOIN master.process_stages ps ON ps.id=sb.process_stage_id
                     AND ps.company_id=sb.company_id AND ps.is_active=TRUE
                   JOIN master.item_variants v ON v.id=sb.item_variant_id
                   JOIN master.items i ON i.id=v.item_id
                   LEFT JOIN master.brands b ON b.id=v.brand_id
                   LEFT JOIN master.shades sh ON sh.id=v.shade_id
                   WHERE sb.company_id=%s AND ps.code = ANY(%s) AND i.item_code='NALKI'
                     AND i.is_active=TRUE AND v.is_active=TRUE
                     AND sb.ownership_type_id=1 AND sb.owner_party_id IS NULL
                   GROUP BY v.id,v.variant_code,v.variant_name,b.name,sh.shade_code,sh.shade_name
                   HAVING SUM(sb.quantity)>=%s
                   ORDER BY b.name,sh.shade_code,v.variant_code""",
                (int(company_id), list(ELIGIBLE_PACKING_SOURCE_STAGE_CODES), PIECES_PER_FINISHED_BOX),
            )
            variants = [dict(row) for row in cur.fetchall()]
    return {"variants": variants}


def get_packing_page_data(company_id: int, search: str = "") -> dict:
    search = str(search or "").strip()[:100]
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) AS total
                   FROM production.packing_orders po
                   WHERE po.company_id=%s
                     AND (%s='' OR po.packing_no ILIKE %s OR po.status ILIKE %s)""",
                (int(company_id), search, f"%{search}%", f"%{search}%"),
            )
            total = int(cur.fetchone()["total"])
            cur.execute(
                """SELECT po.id,po.packing_no,po.packing_date,po.status,
                          po.planned_quantity_boxes AS finished_boxes,
                          po.planned_quantity_pieces,po.created_at,
                          (SELECT COUNT(*) FROM production.packing_order_items pi
                           WHERE pi.packing_order_id=po.id) AS item_count,
                          (SELECT string_agg(DISTINCT b.name, ', ' ORDER BY b.name)
                           FROM production.packing_order_items pi
                           LEFT JOIN master.brands b ON b.id=pi.brand_id
                           WHERE pi.packing_order_id=po.id) AS brands,
                          (SELECT CASE WHEN pcs.source='APPROVED_VERSION'
                                  THEN pcs.config_key || ' · v' || pcs.configuration_version_id::text
                                  ELSE pcs.config_key || ' · System default'
                             END
                           FROM production.packing_configuration_snapshots pcs
                           WHERE pcs.packing_order_id=po.id
                             AND pcs.config_type='PACKAGING_RULE'
                           LIMIT 1) AS packaging_rule
                   FROM production.packing_orders po
                   WHERE po.company_id=%s
                     AND (%s='' OR po.packing_no ILIKE %s OR po.status ILIKE %s)
                   ORDER BY po.id DESC LIMIT 100""",
                (int(company_id), search, f"%{search}%", f"%{search}%"),
            )
            rows = [dict(row) for row in cur.fetchall()]
    return {"rows": rows, "total": total, "search": search}


def create_packing_order_draft(
    *, company_id: int, user_id: int, user: dict, request: Any,
    packing_date: str, lines: list[dict[str, Any]], remarks: str = "",
) -> dict:
    """Create a DRAFT plan only. Does not reserve, consume, or move inventory."""
    if int(user.get("id", 0)) != int(user_id) or int(user.get("company_id", 0)) != int(company_id):
        raise ValueError("Packing draft actor/company context is invalid.")
    parsed_date = parse_packing_date(packing_date)
    normalized = normalize_packing_lines(lines)
    remarks = str(remarks or "").strip()
    if len(remarks) > 2000:
        raise ValueError("Remarks cannot exceed 2,000 characters.")

    total_finished_boxes = sum(row["finished_boxes_qty"] for row in normalized)
    total_pieces = sum(row["quantity_pieces"] for row in normalized)
    if total_finished_boxes <= 0 or total_pieces <= 0:
        raise ValueError("Packing quantities must be greater than zero.")

    note = (
        "Packaging snapshot: 100 pieces per finished wall box; "
        "10 small boxes per finished wall box; 10 pieces per small box. "
        "Weight and costing are intentionally not calculated in this draft-only phase. "
        "Draft does not reserve, consume, or move stock."
    )
    combined_remarks = f"{remarks}\n{note}" if remarks else note

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                lock_key = f"packing:{int(company_id)}:{parsed_date.isoformat()}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
                for row in normalized:
                    cur.execute(
                        """SELECT v.id,v.brand_id,v.shade_id,
                                  COALESCE((SELECT SUM(sb.quantity)
                                    FROM inventory.stock_balances sb
                                    JOIN inventory.locations il ON il.id=sb.location_id
                                      AND il.is_active=TRUE AND il.allow_stock=TRUE
                                    JOIN master.process_stages ps ON ps.id=sb.process_stage_id
                                      AND ps.company_id=sb.company_id AND ps.is_active=TRUE
                                    WHERE sb.company_id=%s AND sb.item_variant_id=v.id
                                      AND ps.code=ANY(%s)
                                      AND sb.ownership_type_id=1 AND sb.owner_party_id IS NULL),0)
                                    AS available_pieces
                           FROM master.item_variants v
                           JOIN master.items i ON i.id=v.item_id
                           WHERE v.id=%s AND v.is_active=TRUE
                             AND i.item_code='NALKI' AND i.is_active=TRUE""",
                        (int(company_id), list(ELIGIBLE_PACKING_SOURCE_STAGE_CODES), row["item_variant_id"]),
                    )
                    variant = cur.fetchone()
                    if not variant:
                        raise ValueError("Only active Nalki item variants can be packed.")
                    validate_packing_source_quantity(row["quantity_pieces"], variant["available_pieces"])
                    row["brand_id"] = variant["brand_id"]
                    row["shade_id"] = variant["shade_id"]

                cur.execute(
                    """SELECT COALESCE(MAX(id),0)+1 AS next_id
                       FROM production.packing_orders WHERE company_id=%s""",
                    (int(company_id),),
                )
                next_id = int(cur.fetchone()["next_id"])
                packing_no = f"PKG-{parsed_date:%Y%m%d}-{next_id:05d}"
                cur.execute(
                    """INSERT INTO production.packing_orders
                       (company_id,packing_no,packing_date,location_id,status,
                        planned_quantity_boxes,planned_quantity_pieces,
                        labour_cost,total_material_cost,total_process_cost,total_cost,
                        remarks,created_by)
                       VALUES (%s,%s,%s,NULL,'DRAFT',%s,%s,0,0,0,0,%s,%s)
                       RETURNING id,packing_no,packing_date,status,
                                 planned_quantity_boxes,planned_quantity_pieces""",
                    (int(company_id), packing_no, parsed_date,
                     total_finished_boxes, total_pieces, combined_remarks, int(user_id)),
                )
                order = dict(cur.fetchone())
                packaging_snapshot = resolve_nalki_packaging_snapshot(
                    cur, company_id=int(company_id), effective_on=parsed_date
                )
                insert_packing_configuration_snapshot(
                    cur, company_id=int(company_id), packing_order_id=order["id"],
                    user_id=int(user_id), snapshot=packaging_snapshot,
                )
                for row in normalized:
                    cur.execute(
                        """INSERT INTO production.packing_order_items
                           (packing_order_id,item_variant_id,brand_id,shade_id,
                            piece_weight_g,stock_type,source_type,quantity_pieces,
                            boxes_qty,pieces_per_box,gross_weight_kg,net_weight_kg,
                            status,notes,ownership_type_id,owner_party_id)
                           VALUES (%s,%s,%s,%s,0,'OWN','EXISTING_STOCK',%s,%s,10,0,0,
                                   'PENDING',%s,1,NULL)""",
                        (order["id"], row["item_variant_id"], row["brand_id"],
                         row["shade_id"], row["quantity_pieces"], row["small_boxes_qty"],
                         "Finished wall boxes: %s; small boxes: %s; 10 pieces per small box. Weight/cost pending."
                         % (row["finished_boxes_qty"], row["small_boxes_qty"])),
                    )
                cur.execute(
                    """INSERT INTO production.packing_order_status_history
                       (packing_order_id,old_status,new_status,changed_by,reason,notes)
                       VALUES (%s,NULL,'DRAFT',%s,%s,%s)""",
                    (order["id"], int(user_id), "Packing draft created; no stock movement.", combined_remarks),
                )
                write_audit_log(
                    conn,
                    user=user,
                    request=request,
                    action="CREATE_DRAFT",
                    table_name="production.packing_orders",
                    record_id=order["id"],
                    document_no=order["packing_no"],
                    new_values={
                        "status": "DRAFT",
                        "planned_finished_boxes": total_finished_boxes,
                        "planned_pieces": total_pieces,
                        "small_boxes_per_finished_box": SMALL_BOXES_PER_FINISHED_BOX,
                        "pieces_per_small_box": PIECES_PER_SMALL_BOX,
                        "packaging_config_source": packaging_snapshot["source"],
                        "packaging_config_version_id": packaging_snapshot["configuration_version_id"],
                        "packaging_config_payload": packaging_snapshot["payload"],
                    },
                    reason="Packing draft created; no stock movement.",
                    module="PACKING",
                )
    return order
