"""Read-only production overview for the first production UI milestone."""
from __future__ import annotations

from typing import Any
from decimal import Decimal

from psycopg import sql

from .db import get_connection


# Fixed internal allow-list: table names are never accepted from a request.
PROCESS_ORDER_SOURCES = (
    ("production_orders", "Production Planning", "production_orders"),
    ("dyeing", "Dyeing", "dyeing_orders"),
    ("large_cone", "Large Cone (Big Cone)", "big_cone_orders"),
    ("baby_cone", "Baby Cone", "baby_cone_orders"),
    ("rewinding", "Rewinding", "rewinding_orders"),
    ("nalki", "Nalki Production", "nalki_orders"),
    ("outside_dyeing", "Outside Dyeing", "outside_dyeing_orders"),
    ("outside_labeling", "Outside Labeling", "outside_labeling_orders"),
    ("packing", "Packing", "packing_orders"),
)


def _status_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"status": str(row["status"]), "count": int(row["total"])}
        for row in rows
    ]



def _big_cone_register_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize read-only Big Cone register rows without treating balance as wastage."""
    result = []
    for row in rows:
        input_kg = Decimal(str(row.get("input_quantity_kg") or 0))
        output_kg = Decimal(str(row.get("output_quantity_kg") or 0))
        result.append({
            "id": int(row["id"]),
            "big_cone_no": str(row["big_cone_no"]),
            "big_cone_date": row["big_cone_date"],
            "status": str(row["status"]),
            "input_quantity_kg": input_kg,
            "output_quantity_kg": output_kg,
            "unreconciled_difference_kg": input_kg - output_kg,
            "process_cost": Decimal(str(row.get("total_process_cost") or 0)),
            "material_line_count": int(row.get("material_line_count") or 0),
            "output_line_count": int(row.get("output_line_count") or 0),
        })
    return result


def get_production_dashboard_data(company_id: int) -> dict[str, Any]:
    """Read company-scoped production activity and setup readiness only.

    This function deliberately opens a READ ONLY transaction. It does not
    create production records, reserve stock, or mutate workflow state.
    """
    company_id = int(company_id)
    processes: list[dict[str, Any]] = []
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")

                for key, label, table_name in PROCESS_ORDER_SOURCES:
                    cur.execute(
                        sql.SQL("SELECT count(*) AS total FROM production.{} WHERE company_id=%s").format(
                            sql.Identifier(table_name)
                        ),
                        (company_id,),
                    )
                    total = int(cur.fetchone()["total"])
                    cur.execute(
                        sql.SQL(
                            "SELECT status,count(*) AS total FROM production.{} "
                            "WHERE company_id=%s GROUP BY status ORDER BY status"
                        ).format(sql.Identifier(table_name)),
                        (company_id,),
                    )
                    statuses = _status_summary(cur.fetchall())
                    processes.append(
                        {"key": key, "label": label, "total": total, "statuses": statuses}
                    )

                cur.execute(
                    """SELECT count(*) AS total
                       FROM production.production_executions e
                       JOIN production.production_orders o ON o.id=e.production_order_id
                       WHERE o.company_id=%s""",
                    (company_id,),
                )
                executions = int(cur.fetchone()["total"])

                cur.execute(
                    "SELECT count(*) AS total FROM production.recipes WHERE company_id=%s",
                    (company_id,),
                )
                recipes = int(cur.fetchone()["total"])
                cur.execute(
                    "SELECT count(*) AS total FROM production.production_targets WHERE company_id=%s",
                    (company_id,),
                )
                targets = int(cur.fetchone()["total"])

                cur.execute(
                    """SELECT o.id, o.dyeing_no, o.dyeing_date, o.status,
                              COUNT(l.id) AS line_count,
                              COUNT(l.id) FILTER (WHERE s.status='PENDING_CONFIGURATION') AS pending_conversion_count,
                              COUNT(l.id) FILTER (WHERE s.status='BLOCKED_PRECISION') AS blocked_conversion_count,
                              COUNT(l.id) FILTER (WHERE l.id IS NOT NULL AND s.id IS NULL) AS missing_snapshot_count
                       FROM production.dyeing_orders o
                       LEFT JOIN production.dyeing_consumption_lines l ON l.dyeing_order_id=o.id
                       LEFT JOIN production.dyeing_unit_conversion_snapshots s
                         ON s.consumption_line_id=l.id AND s.company_id=o.company_id
                       WHERE o.company_id=%s
                       GROUP BY o.id, o.dyeing_no, o.dyeing_date, o.status, o.created_at
                       ORDER BY o.created_at DESC, o.id DESC
                       LIMIT 10""",
                    (company_id,),
                )
                recent_dyeing_orders = [
                    {
                        "id": int(row["id"]),
                        "dyeing_no": str(row["dyeing_no"]),
                        "dyeing_date": row["dyeing_date"],
                        "status": str(row["status"]),
                        "line_count": int(row["line_count"]),
                        "pending_conversion_count": int(row["pending_conversion_count"]),
                        "blocked_conversion_count": int(row["blocked_conversion_count"]),
                        "missing_snapshot_count": int(row["missing_snapshot_count"]),
                    }
                    for row in cur.fetchall()
                ]

                cur.execute(
                    """SELECT o.id,o.big_cone_no,o.big_cone_date,o.status,
                              o.input_quantity_kg,o.output_quantity_kg,o.total_process_cost,
                              (SELECT count(*) FROM production.big_cone_material_lines ml
                               WHERE ml.big_cone_order_id=o.id) AS material_line_count,
                              (SELECT count(*) FROM production.big_cone_output_lines ol
                               WHERE ol.big_cone_order_id=o.id) AS output_line_count
                       FROM production.big_cone_orders o
                       WHERE o.company_id=%s
                       ORDER BY o.created_at DESC,o.id DESC
                       LIMIT 10""",
                    (company_id,),
                )
                recent_big_cone_orders = _big_cone_register_rows(cur.fetchall())

                cur.execute(
                    "SELECT count(*) AS total FROM master.machines WHERE company_id=%s AND is_active=true",
                    (company_id,),
                )
                active_machines = int(cur.fetchone()["total"])
                cur.execute(
                    "SELECT count(*) AS total FROM core.departments WHERE company_id=%s AND is_active=true",
                    (company_id,),
                )
                active_departments = int(cur.fetchone()["total"])
                cur.execute(
                    "SELECT id,code,name,sequence_no FROM master.process_stages "
                    "WHERE company_id=%s AND is_active=true ORDER BY sequence_no,id",
                    (company_id,),
                )
                stages = [
                    {
                        "id": int(row["id"]),
                        "code": str(row["code"]),
                        "name": str(row["name"]),
                        "sequence_no": int(row["sequence_no"]),
                    }
                    for row in cur.fetchall()
                ]

    return {
        "processes": processes,
        "production_order_count": processes[0]["total"],
        "executions": executions,
        "recipes": recipes,
        "targets": targets,
        "recent_dyeing_orders": recent_dyeing_orders,
        "recent_big_cone_orders": recent_big_cone_orders,
        "active_machines": active_machines,
        "active_departments": active_departments,
        "active_process_stages": len(stages),
        "process_stages": stages,
        "setup_ready": active_machines > 0 and active_departments > 0,
    }
