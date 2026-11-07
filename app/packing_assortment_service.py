"""Draft-only 100-shade Nalki assortment packing workflow."""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from .db import get_connection
from .audit_service import write_audit_log
from .configuration_runtime_service import resolve_nalki_packaging_snapshot, insert_packing_configuration_snapshot
from .packing_service import (
    ELIGIBLE_PACKING_SOURCE_STAGE_CODES,
    PIECES_PER_FINISHED_BOX,
    SMALL_BOXES_PER_FINISHED_BOX,
    parse_packing_date,
)

EXPECTED_ASSORTMENT_SHADES = 100
VALID_SHADE_CODES = frozenset([str(n) for n in range(1, 901)] + ["3000", "3001", "3002"])


def normalize_assortment_shade_codes(value: Any) -> list[str]:
    """Parse exactly 100 distinct shade codes from comma/space/newline separated input."""
    raw = str(value or "").strip()
    codes = [part for part in re.split(r"[,;\s]+", raw) if part]
    if len(codes) != EXPECTED_ASSORTMENT_SHADES:
        raise ValueError("Enter exactly 100 shade codes for each finished assortment box.")
    if any(code not in VALID_SHADE_CODES for code in codes):
        raise ValueError("Shade codes must be 1–900, 3000 (Black), 3001 (White), or 3002 (Off White).")
    if len(set(codes)) != EXPECTED_ASSORTMENT_SHADES:
        raise ValueError("Duplicate shade code found. Every finished box needs 100 unique shades.")
    return codes


def get_packing_assortment_form_data(company_id: int) -> dict[str, Any]:
    """Return active Nalki brands and read-only stock coverage in eligible process stages."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT b.id AS brand_id,b.name AS brand_name,
                          COUNT(DISTINCT sh.id) AS shade_count,
                          COUNT(DISTINCT v.shade_id) AS nalki_variant_shades
                   FROM master.brands b
                   JOIN master.shades sh ON sh.brand_id=b.id AND sh.is_active=TRUE
                   JOIN master.item_variants v ON v.brand_id=b.id AND v.shade_id=sh.id
                     AND v.is_active=TRUE
                   JOIN master.items i ON i.id=v.item_id
                     AND i.company_id=%s AND i.item_code='NALKI' AND i.is_active=TRUE
                   WHERE b.is_active=TRUE
                   GROUP BY b.id,b.name
                   ORDER BY b.name""",
                (int(company_id),),
            )
            brands = [dict(row) for row in cur.fetchall()]
            cur.execute(
                """WITH own_stage_stock AS (
                     SELECT sb.item_variant_id,SUM(sb.quantity) AS available_pieces
                     FROM inventory.stock_balances sb
                     JOIN inventory.locations il ON il.id=sb.location_id
                       AND il.is_active=TRUE AND il.allow_stock=TRUE
                     JOIN master.process_stages ps ON ps.id=sb.process_stage_id
                       AND ps.company_id=sb.company_id AND ps.is_active=TRUE
                       AND ps.code=ANY(%s)
                     WHERE sb.company_id=%s AND sb.ownership_type_id=1
                       AND sb.owner_party_id IS NULL
                     GROUP BY sb.item_variant_id
                   )
                   SELECT v.brand_id,COUNT(DISTINCT v.shade_id) AS available_shades,
                          COALESCE(SUM(s.available_pieces),0) AS available_pieces
                   FROM master.item_variants v
                   JOIN master.items i ON i.id=v.item_id
                     AND i.company_id=%s AND i.item_code='NALKI' AND i.is_active=TRUE
                   JOIN master.shades sh ON sh.id=v.shade_id AND sh.is_active=TRUE
                   JOIN own_stage_stock s ON s.item_variant_id=v.id
                   WHERE v.is_active=TRUE
                   GROUP BY v.brand_id""",
                (list(ELIGIBLE_PACKING_SOURCE_STAGE_CODES), int(company_id), int(company_id)),
            )
            stock = {int(row["brand_id"]): dict(row) for row in cur.fetchall()}
    for brand in brands:
        coverage = stock.get(int(brand["brand_id"]), {})
        brand["available_shades"] = int(coverage.get("available_shades", 0))
        brand["available_pieces"] = coverage.get("available_pieces", 0)
    return {"brands": brands, "expected_shades": EXPECTED_ASSORTMENT_SHADES}


def create_packing_assortment_draft(
    *, company_id: int, user_id: int, user: dict, request: Any,
    packing_date: str, brand_id: Any, finished_boxes_qty: Any,
    shade_codes: Any, remarks: str = "",
) -> dict[str, Any]:
    """Create one DRAFT with 100 shade rows; never reserves or moves inventory."""
    if int(user.get("id", 0)) != int(user_id) or int(user.get("company_id", 0)) != int(company_id):
        raise ValueError("Packing draft actor/company context is invalid.")
    parsed_date = parse_packing_date(packing_date)
    codes = normalize_assortment_shade_codes(shade_codes)
    try:
        selected_brand_id = int(str(brand_id).strip())
        box_count = int(str(finished_boxes_qty).strip())
    except (TypeError, ValueError):
        raise ValueError("Select a brand and enter a positive whole finished-box quantity.")
    if selected_brand_id <= 0 or box_count <= 0 or box_count > 100000:
        raise ValueError("Select a brand and enter a positive whole finished-box quantity.")
    remarks = str(remarks or "").strip()
    if len(remarks) > 2000:
        raise ValueError("Remarks cannot exceed 2,000 characters.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                lock_key = f"packing-assortment:{int(company_id)}:{parsed_date.isoformat()}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
                cur.execute(
                    """WITH own_stage_stock AS (
                         SELECT sb.item_variant_id,SUM(sb.quantity) AS available_pieces
                         FROM inventory.stock_balances sb
                         JOIN inventory.locations il ON il.id=sb.location_id
                           AND il.is_active=TRUE AND il.allow_stock=TRUE
                         JOIN master.process_stages ps ON ps.id=sb.process_stage_id
                           AND ps.company_id=sb.company_id AND ps.is_active=TRUE
                           AND ps.code=ANY(%s)
                         WHERE sb.company_id=%s AND sb.ownership_type_id=1
                           AND sb.owner_party_id IS NULL
                         GROUP BY sb.item_variant_id
                       )
                       SELECT v.id AS item_variant_id,v.brand_id,v.shade_id,
                              sh.shade_code,sh.shade_name,b.name AS brand_name,
                              COALESCE(s.available_pieces,0) AS available_pieces
                       FROM master.item_variants v
                       JOIN master.items i ON i.id=v.item_id
                         AND i.company_id=%s AND i.item_code='NALKI' AND i.is_active=TRUE
                       JOIN master.brands b ON b.id=v.brand_id AND b.is_active=TRUE
                       JOIN master.shades sh ON sh.id=v.shade_id
                         AND sh.brand_id=b.id AND sh.is_active=TRUE
                       LEFT JOIN own_stage_stock s ON s.item_variant_id=v.id
                       WHERE v.is_active=TRUE AND v.brand_id=%s
                         AND sh.shade_code=ANY(%s)
                       ORDER BY sh.shade_code::integer""",
                    (list(ELIGIBLE_PACKING_SOURCE_STAGE_CODES), int(company_id),
                     int(company_id), selected_brand_id, codes),
                )
                variants = [dict(row) for row in cur.fetchall()]
                if len(variants) != EXPECTED_ASSORTMENT_SHADES:
                    raise ValueError(
                        "Selected brand does not have exactly one active Nalki variant for every selected shade code."
                    )
                if len({int(row["shade_id"]) for row in variants}) != EXPECTED_ASSORTMENT_SHADES:
                    raise ValueError("Selected shade codes do not resolve to 100 unique master shades.")
                insufficient = [
                    f"{row['shade_code']} ({row['available_pieces']} available)"
                    for row in variants if row["available_pieces"] < box_count
                ]
                if insufficient:
                    preview = ", ".join(insufficient[:12])
                    suffix = f" and {len(insufficient)-12} more" if len(insufficient) > 12 else ""
                    raise ValueError(
                        f"Insufficient OWN stock for {len(insufficient)} selected shade(s); "
                        f"{box_count} piece(s) per shade required: {preview}{suffix}."
                    )

                total_pieces = EXPECTED_ASSORTMENT_SHADES * box_count
                regular_boxes = SMALL_BOXES_PER_FINISHED_BOX * box_count
                note = (
                    "100-shade assortment: one piece of each of 100 unique shades from one brand "
                    f"per finished 100-piece box; finished boxes={box_count}; "
                    f"regular 10-piece boxes required={regular_boxes}. "
                    "Regular boxes are a separate packaging material; finished 100-piece box is a separate product pack. "
                    "OWN stock only. Draft does not reserve, consume, or move stock. Weight/cost pending."
                )
                combined_remarks = f"{remarks}\n{note}" if remarks else note
                cur.execute(
                    "SELECT COALESCE(MAX(id),0)+1 AS next_id FROM production.packing_orders WHERE company_id=%s",
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
                    (int(company_id), packing_no, parsed_date, box_count, total_pieces,
                     combined_remarks, int(user_id)),
                )
                order = dict(cur.fetchone())
                packaging_snapshot = resolve_nalki_packaging_snapshot(
                    cur, company_id=int(company_id), effective_on=parsed_date
                )
                insert_packing_configuration_snapshot(
                    cur, company_id=int(company_id), packing_order_id=order["id"],
                    user_id=int(user_id), snapshot=packaging_snapshot,
                )
                for row in variants:
                    cur.execute(
                        """INSERT INTO production.packing_order_items
                           (packing_order_id,item_variant_id,brand_id,shade_id,
                            piece_weight_g,stock_type,source_type,quantity_pieces,
                            boxes_qty,pieces_per_box,gross_weight_kg,net_weight_kg,
                            status,notes,ownership_type_id,owner_party_id)
                           VALUES (%s,%s,%s,%s,0,'OWN','EXISTING_STOCK',%s,%s,1,0,0,
                                   'PENDING',%s,1,NULL)""",
                        (order["id"], row["item_variant_id"], row["brand_id"], row["shade_id"],
                         box_count, box_count,
                         f"100-shade assortment: 1 piece per finished box; shade {row['shade_code']}; "
                         f"{box_count} finished box(es); regular 10-piece boxes are tracked separately."),
                    )
                cur.execute(
                    """INSERT INTO production.packing_order_status_history
                       (packing_order_id,old_status,new_status,changed_by,reason,notes)
                       VALUES (%s,NULL,'DRAFT',%s,%s,%s)""",
                    (order["id"], int(user_id), "100-shade assortment draft created; no stock movement.", combined_remarks),
                )
                write_audit_log(
                    conn, user=user, request=request, action="CREATE_DRAFT",
                    table_name="production.packing_orders", record_id=order["id"],
                    document_no=order["packing_no"],
                    new_values={
                        "status": "DRAFT",
                        "packing_type": "100_SHADE_ASSORTMENT",
                        "brand_id": selected_brand_id,
                        "unique_shades": EXPECTED_ASSORTMENT_SHADES,
                        "planned_finished_boxes": box_count,
                        "planned_pieces": total_pieces,
                        "regular_10_piece_boxes_required": regular_boxes,
                        "packaging_config_source": packaging_snapshot["source"],
                        "packaging_config_version_id": packaging_snapshot["configuration_version_id"],
                        "packaging_config_payload": packaging_snapshot["payload"],
                    },
                    reason="100-shade assortment draft created; no stock movement.",
                    module="PACKING",
                )
    return order