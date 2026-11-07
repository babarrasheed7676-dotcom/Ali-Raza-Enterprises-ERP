"""Read-only Baby Cone source preflight from POSTED Large Cone output lines.

This milestone does not create orders, reserve stock, save costs, or post inventory.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from .db import get_connection


def _baby_cone_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize exact source dimensions and distinguish source availability blockers."""
    result = []
    for row in rows:
        source_qty = Decimal(str(row.get("source_quantity_kg") or 0))
        allocated = Decimal(str(row.get("allocated_kg") or 0))
        stock_qty = Decimal(str(row.get("current_source_stock_kg") or 0))
        available = min(source_qty - allocated, stock_qty - allocated)
        ownership = str(row.get("ownership_code") or "").upper()
        party_rate_missing = ownership == "PARTY" and row.get("unit_cost") is None
        result.append({
            "source_output_line_id": int(row["source_output_line_id"]),
            "big_cone_order_id": int(row["big_cone_order_id"]),
            "big_cone_no": str(row["big_cone_no"]),
            "big_cone_date": row["big_cone_date"],
            "line_no": int(row["line_no"]),
            "item_code": str(row["item_code"]),
            "item_name": str(row["item_name"]),
            "variant_code": str(row["variant_code"]),
            "batch_no": row.get("batch_no"),
            "ownership_code": ownership,
            "party_name": row.get("party_name"),
            "unit_code": str(row["unit_code"]),
            "source_quantity_kg": source_qty,
            "allocated_kg": allocated,
            "current_source_stock_kg": stock_qty,
            "available_kg": max(Decimal("0"), available),
            "unit_cost": Decimal(str(row["unit_cost"])) if row.get("unit_cost") is not None else None,
            "party_rate_missing": party_rate_missing,
            "eligible": available > 0 and not party_rate_missing,
        })
    return result


def get_baby_cone_draft_source_preflight(company_id: int) -> dict[str, Any]:
    """Inspect POSTED Large Cone outputs at the one RAW_STORE/BIG_CONE stock dimension."""
    company_id = int(company_id)
    if company_id <= 0:
        raise ValueError("A valid company is required.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT il.id AS location_id
                       FROM inventory.locations il
                       JOIN core.locations cl ON cl.id=il.core_location_id
                       WHERE cl.company_id=%s AND cl.code='RAW_STORE'
                         AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE""",
                    (company_id,),
                )
                location = cur.fetchone()
                cur.execute(
                    "SELECT id FROM master.process_stages WHERE company_id=%s AND code='BIG_CONE' AND is_active=TRUE",
                    (company_id,),
                )
                big_cone_stage = cur.fetchone()
                cur.execute(
                    "SELECT id FROM master.process_stages WHERE company_id=%s AND code='BABY_CONE' AND is_active=TRUE",
                    (company_id,),
                )
                baby_cone_stage = cur.fetchone()

                sources = []
                if location and big_cone_stage and baby_cone_stage:
                    cur.execute(
                        """SELECT ol.id AS source_output_line_id,o.id AS big_cone_order_id,
                                  o.big_cone_no,o.big_cone_date,ol.line_no,
                                  ol.item_variant_id,ol.batch_id,ol.location_id,
                                  ol.ownership_type_id,ol.owner_party_id,ol.process_stage_id,
                                  ol.quantity_kg AS source_quantity_kg,
                                  ol.unit_cost,ol.unit_id,u.code AS unit_code,
                                  own.code AS ownership_code,p.party_name,
                                  i.item_code,i.item_name,v.variant_code,
                                  b.batch_no,COALESCE(sb.quantity,0) AS current_source_stock_kg,
                                  COALESCE((
                                    SELECT SUM(ml.quantity_kg)
                                    FROM production.baby_cone_material_lines ml
                                    JOIN production.baby_cone_orders bo ON bo.id=ml.baby_cone_order_id
                                    WHERE ml.source_big_cone_output_line_id=ol.id
                                      AND bo.status IN ('DRAFT','APPROVED')
                                  ),0) AS allocated_kg
                           FROM production.big_cone_output_lines ol
                           JOIN production.big_cone_orders o ON o.id=ol.big_cone_order_id
                           JOIN master.item_variants v ON v.id=ol.item_variant_id
                           JOIN master.items i ON i.id=v.item_id
                           JOIN master.ownership_types own ON own.id=ol.ownership_type_id
                           JOIN master.units u ON u.id=ol.unit_id
                           LEFT JOIN inventory.batches b ON b.id=ol.batch_id
                           LEFT JOIN master.parties p ON p.id=ol.owner_party_id
                           LEFT JOIN inventory.stock_balances sb
                             ON sb.company_id=o.company_id
                            AND sb.item_variant_id=ol.item_variant_id
                            AND sb.batch_id IS NOT DISTINCT FROM ol.batch_id
                            AND sb.location_id IS NOT DISTINCT FROM ol.location_id
                            AND sb.ownership_type_id=ol.ownership_type_id
                            AND sb.owner_party_id IS NOT DISTINCT FROM ol.owner_party_id
                            AND sb.process_stage_id=ol.process_stage_id
                           WHERE o.company_id=%s AND o.status='POSTED'
                             AND ol.destination_type='BABY_CONE'
                             AND ol.location_id=%s AND ol.process_stage_id=%s
                             AND i.item_code='YARN' AND i.is_active=TRUE AND v.is_active=TRUE
                             AND own.code IN ('OWN','PARTY')
                             AND u.code='KG' AND u.is_active=TRUE
                           ORDER BY o.big_cone_date DESC,o.id DESC,ol.line_no""",
                        (company_id, int(location["location_id"]), int(big_cone_stage["id"])),
                    )
                    sources = _baby_cone_source_rows([dict(row) for row in cur.fetchall()])

                cur.execute(
                    "SELECT id,code,name FROM core.departments WHERE company_id=%s AND is_active=TRUE ORDER BY name,id",
                    (company_id,),
                )
                departments = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT id,machine_code,machine_name,machine_type,department_id
                       FROM master.machines WHERE company_id=%s AND is_active=TRUE
                       ORDER BY machine_code,id""",
                    (company_id,),
                )
                machines = [dict(row) for row in cur.fetchall()]

    return {
        "sources": sources,
        "eligible_source_count": sum(1 for row in sources if row["eligible"]),
        "blocked_source_count": sum(1 for row in sources if not row["eligible"]),
        "departments": departments,
        "machines": machines,
        "raw_store_ready": bool(location),
        "big_cone_stage_ready": bool(big_cone_stage),
        "baby_cone_stage_ready": bool(baby_cone_stage),
        "source_ready": bool(sources) and any(row["eligible"] for row in sources),
        "setup_ready": bool(location and big_cone_stage and baby_cone_stage and departments and machines),
        "read_only": True,
        "draft_creation_enabled": False,
        "stock_reserved": False,
        "stock_posted": False,
    }
