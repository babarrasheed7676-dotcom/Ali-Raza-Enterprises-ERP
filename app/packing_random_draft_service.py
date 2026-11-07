"""Transactional DRAFT-only persistence for random 100-piece Nalki packing."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from .audit_service import write_audit_log
from .db import get_connection
from .packing_random_service import (
    RANDOM_SOURCE_FRESH,
    RANDOM_SOURCE_PARTY_REJECTED_USABLE,
    SOURCE_TABLE_BY_TYPE,
    validate_random_100_allocations,
)
from .packing_random_source_service import get_random_packing_source_candidates
from .packing_service import parse_packing_date
from .configuration_runtime_service import resolve_nalki_packaging_snapshot, insert_packing_configuration_snapshot


def _positive_int(value: Any, label: str, maximum: int = 100000) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f"{label} must be a positive whole number.")
    if number <= 0 or number > maximum:
        raise ValueError(f"{label} must be a positive whole number.")
    return number


def _selected_candidates(
    candidates: list[dict[str, Any]], submitted: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not isinstance(submitted, list) or not 1 <= len(submitted) <= 500:
        raise ValueError("Provide source allocations for exactly 100 unique shades.")
    by_key = {
        (str(row["source_type"]), int(row["source_line_id"])): row
        for row in candidates
    }
    selected = []
    seen = set()
    for index, raw in enumerate(submitted, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"Allocation {index} is invalid.")
        source_type = str(raw.get("source_type", "")).strip().upper()
        source_id = _positive_int(raw.get("source_line_id"), f"Allocation {index} source line ID")
        key = (source_type, source_id)
        if key in seen:
            raise ValueError(f"Allocation {index} duplicates a source line.")
        seen.add(key)
        candidate = by_key.get(key)
        if candidate is None:
            raise ValueError(f"Allocation {index} is not an eligible live source line.")
        row = dict(candidate)
        row["quantity_pieces"] = raw.get("quantity_pieces")
        selected.append(row)
    return selected


def create_random_packing_draft(
    *,
    company_id: int,
    user_id: int,
    user: dict[str, Any],
    request: Any,
    packing_date: str,
    finished_boxes_qty: Any,
    allocations: list[dict[str, Any]],
    remarks: str = "",
) -> dict[str, Any]:
    """Create a DRAFT and persist one traceable item/allocation per source line.

    The function locks source lines and matching stock-balance rows while it
    validates and saves. It does not reserve, issue, consume, transfer, post,
    or account for inventory. Availability must be checked again at approval
    and posting because DRAFTs do not reserve stock.
    """
    company_id = int(company_id)
    user_id = int(user_id)
    if int(user.get("id", 0)) != user_id or int(user.get("company_id", 0)) != company_id:
        raise ValueError("Packing draft actor/company context is invalid.")
    if company_id <= 0 or user_id <= 0:
        raise ValueError("A valid company and user are required.")
    parsed_date = parse_packing_date(packing_date)
    boxes = _positive_int(finished_boxes_qty, "Finished random-box quantity")
    remarks = str(remarks or "").strip()
    if len(remarks) > 2000:
        raise ValueError("Remarks cannot exceed 2,000 characters.")

    with get_connection() as conn:
        with conn.transaction():
            # Serialize document numbers and source allocation creation per company.
            lock_key = f"packing-random:{company_id}:{parsed_date.isoformat()}"
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))

            current_candidates = get_random_packing_source_candidates(
                company_id, connection=conn
            )
            selected = _selected_candidates(current_candidates, allocations)

            # Lock every chosen production source line.
            for row in selected:
                source_type = row["source_type"]
                table = SOURCE_TABLE_BY_TYPE[source_type]
                with conn.cursor() as cur:
                    cur.execute(
                        f"SELECT id FROM {table} WHERE id=%s FOR UPDATE",
                        (int(row["source_line_id"]),),
                    )
                    if cur.fetchone() is None:
                        raise ValueError("A selected source line changed; reload source availability.")

            # Lock all balance rows in the exact source buckets.
            for row in selected:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT id FROM inventory.stock_balances
                           WHERE company_id=%s AND item_variant_id=%s
                             AND batch_id IS NOT DISTINCT FROM %s
                             AND location_id=%s
                             AND process_stage_id IS NOT DISTINCT FROM %s
                             AND ownership_type_id=%s
                             AND owner_party_id IS NOT DISTINCT FROM %s
                             AND quantity>0
                           FOR UPDATE""",
                        (
                            company_id, row["item_variant_id"], row.get("batch_id"),
                            row["location_id"], row["process_stage_id"],
                            row["ownership_type_id"], row.get("owner_party_id"),
                        ),
                    )
                    if not cur.fetchall():
                        raise ValueError("A selected stock bucket changed; reload source availability.")

            # Re-read after locks; never trust availability submitted by the browser.
            locked_candidates = get_random_packing_source_candidates(
                company_id, connection=conn
            )
            selected = _selected_candidates(locked_candidates, allocations)
            normalized = validate_random_100_allocations(selected, boxes)

            total_pieces = 100 * boxes
            fresh_count = sum(1 for row in normalized if row["source_type"] == RANDOM_SOURCE_FRESH)
            return_count = sum(1 for row in normalized if row["source_type"] == RANDOM_SOURCE_PARTY_REJECTED_USABLE)
            total_source_cost = sum(
                (Decimal(row["total_source_cost"]) for row in normalized),
                Decimal("0"),
            )

            note = (
                "Random 100-piece finished box: exactly 100 unique shades, one piece of each shade "
                "per finished box. Source-line allocations retain original ownership, batch, stage "
                "and source cost. Source-cost values are snapshots only, not a posting. "
                "No stock reservation, consumption, transfer, labour or accounting entry is created."
            )
            combined_remarks = f"{remarks}\n{note}" if remarks else note

            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(MAX(id),0)+1 AS next_id
                       FROM production.packing_orders WHERE company_id=%s""",
                    (company_id,),
                )
                next_id = int(cur.fetchone()["next_id"])
                packing_no = f"PKG-RND-{parsed_date:%Y%m%d}-{next_id:05d}"
                cur.execute(
                    """INSERT INTO production.packing_orders
                       (company_id,packing_no,packing_date,location_id,status,
                        planned_quantity_boxes,planned_quantity_pieces,
                        labour_cost,total_material_cost,total_process_cost,total_cost,
                        remarks,created_by)
                       VALUES (%s,%s,%s,NULL,'DRAFT',%s,%s,0,0,0,0,%s,%s)
                       RETURNING id,packing_no,packing_date,status,
                                 planned_quantity_boxes,planned_quantity_pieces""",
                    (
                        company_id, packing_no, parsed_date, boxes, total_pieces,
                        combined_remarks, user_id,
                    ),
                )
                order = dict(cur.fetchone())
                packaging_snapshot = resolve_nalki_packaging_snapshot(
                    cur, company_id=company_id, effective_on=parsed_date
                )
                insert_packing_configuration_snapshot(
                    cur, company_id=company_id, packing_order_id=order["id"],
                    user_id=user_id, snapshot=packaging_snapshot,
                )

            for row in normalized:
                stock_type = "OWN" if row["ownership_type_id"] == 1 else "PARTY"
                item_source_type = (
                    "NALKI_PRODUCTION"
                    if row["source_type"] == RANDOM_SOURCE_FRESH
                    else "OTHER"
                )
                source_id_column = (
                    "nalki_output_line_id"
                    if row["source_type"] == RANDOM_SOURCE_FRESH
                    else "outside_labeling_return_line_id"
                )
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO production.packing_order_items
                           (packing_order_id,item_variant_id,brand_id,shade_id,
                            piece_weight_g,stock_type,source_type,quantity_pieces,
                            boxes_qty,pieces_per_box,gross_weight_kg,net_weight_kg,
                            status,notes,ownership_type_id,owner_party_id)
                           VALUES (%s,%s,%s,%s,0,%s,%s,%s,%s,1,0,0,
                                   'PENDING',%s,%s,%s)
                           RETURNING id""",
                        (
                            order["id"], row["item_variant_id"], row["brand_id"],
                            row["shade_id"], stock_type, item_source_type,
                            row["quantity_pieces"], row["quantity_pieces"],
                            f"Random 100-piece pack; source {row['source_type']} line "
                            f"{row['source_line_id']}; {row['quantity_pieces']} piece(s). "
                            "Weight pending; source cost snapshot is stored in source allocation.",
                            row["ownership_type_id"], row["owner_party_id"],
                        ),
                    )
                    packing_item_id = int(cur.fetchone()["id"])
                    cur.execute(
                        f"""INSERT INTO production.packing_source_allocations
                            (company_id,packing_order_id,packing_order_item_id,source_type,
                             {source_id_column},item_variant_id,batch_id,location_id,
                             process_stage_id,ownership_type_id,owner_party_id,
                             quantity_pieces,source_unit_cost,source_total_cost)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (
                            company_id, order["id"], packing_item_id, row["source_type"],
                            row["source_line_id"], row["item_variant_id"], row.get("batch_id"),
                            row["location_id"], row["process_stage_id"],
                            row["ownership_type_id"], row.get("owner_party_id"),
                            row["quantity_pieces"], row["unit_cost"], row["total_source_cost"],
                        ),
                    )

            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO production.packing_order_status_history
                       (packing_order_id,old_status,new_status,changed_by,reason,notes)
                       VALUES (%s,NULL,'DRAFT',%s,%s,%s)""",
                    (
                        order["id"], user_id,
                        "Random 100-piece packing draft created; no stock movement.",
                        combined_remarks,
                    ),
                )

            write_audit_log(
                conn, user=user, request=request, action="CREATE_RANDOM_DRAFT",
                table_name="production.packing_orders", record_id=order["id"],
                document_no=order["packing_no"],
                new_values={
                    "status": "DRAFT",
                    "packing_type": "RANDOM_100_PIECE",
                    "finished_boxes": boxes,
                    "planned_pieces": total_pieces,
                    "unique_shades": 100,
                    "source_allocation_lines": len(normalized),
                    "fresh_nalki_source_lines": fresh_count,
                    "accepted_party_return_source_lines": return_count,
                    "source_cost_snapshot_total": str(total_source_cost),
                    "stock_reserved": False,
                    "stock_posted": False,
                    "packaging_config_source": packaging_snapshot["source"],
                    "packaging_config_version_id": packaging_snapshot["configuration_version_id"],
                    "packaging_config_payload": packaging_snapshot["payload"],
                },
                reason="Random 100-piece packing draft; no stock movement or accounting posting.",
                module="PACKING",
            )

    return order
