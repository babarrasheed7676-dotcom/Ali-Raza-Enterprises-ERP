"""DRAFT-only Big Cone workflow pinned to posted Dyeing DYED_THREAD output lines.

No inventory balance, batch balance, or ledger is changed by this service.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .db import get_connection
from .audit_service import write_audit_log


DESTINATIONS = {"BABY_CONE", "NALKI", "DIRECT_SALE", "OTHER"}


def _qty(value: Any, label: str, *, allow_zero: bool = False) -> Decimal:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid KG quantity.")
    if not number.is_finite() or number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{label} must be {'zero or greater' if allow_zero else 'greater than zero'}.")
    if number >= Decimal("1000000000000"):
        raise ValueError(f"{label} exceeds the supported quantity range.")
    try:
        rounded = number.quantize(Decimal("0.001"))
    except InvalidOperation:
        raise ValueError(f"{label} exceeds supported KG precision.")
    if number != rounded:
        raise ValueError(f"{label} supports a maximum of 3 decimal places.")
    return number


def _money(value: Any, label: str) -> Decimal:
    try:
        number = Decimal(str(value or "0").strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid PKR amount.")
    if not number.is_finite() or number < 0 or number >= Decimal("100000000000000"):
        raise ValueError(f"{label} must be non-negative and within the supported PKR range.")
    if number != number.quantize(Decimal("0.000001")):
        raise ValueError(f"{label} supports a maximum of 6 decimal places.")
    return number


def normalize_big_cone_lines(lines: list[dict] | None) -> list[dict]:
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("Select between 1 and 100 Dyeing source lines.")
    normalized = []
    seen = set()
    for index, line in enumerate(lines, 1):
        try:
            source_id = int(line.get("source_dyeing_output_line_id"))
        except (TypeError, ValueError):
            raise ValueError(f"Line {index}: select a valid Dyeing output source.")
        if source_id <= 0 or source_id in seen:
            raise ValueError(f"Line {index}: duplicate or invalid Dyeing source line.")
        seen.add(source_id)
        input_kg = _qty(line.get("input_quantity_kg"), f"Line {index} input")
        output_kg = _qty(line.get("output_quantity_kg"), f"Line {index} output")
        if output_kg > input_kg:
            raise ValueError(f"Line {index}: Big Cone output cannot exceed its input quantity.")
        input_cones = _qty(line.get("input_cones") or "0", f"Line {index} input cones", allow_zero=True)
        output_cones = _qty(line.get("output_cones") or "0", f"Line {index} output cones", allow_zero=True)
        if output_cones > input_cones:
            raise ValueError(f"Line {index}: output cones cannot exceed input cones.")
        destination = str(line.get("destination_type") or "").strip().upper()
        if destination not in DESTINATIONS:
            raise ValueError(f"Line {index}: choose a valid Big Cone output destination.")
        normalized.append({
            "line_no": index,
            "source_dyeing_output_line_id": source_id,
            "input_quantity_kg": input_kg,
            "output_quantity_kg": output_kg,
            "input_cones": input_cones,
            "output_cones": output_cones,
            "destination_type": destination,
        })
    return normalized


def get_big_cone_draft_form_data(company_id: int) -> dict[str, Any]:
    company_id = int(company_id)
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
                    "SELECT id FROM master.process_stages WHERE company_id=%s AND code='DYEING' AND is_active=TRUE",
                    (company_id,),
                )
                dyeing_stage = cur.fetchone()
                cur.execute(
                    "SELECT id FROM master.process_stages WHERE company_id=%s AND code='BIG_CONE' AND is_active=TRUE",
                    (company_id,),
                )
                big_cone_stage = cur.fetchone()
                sources = []
                if location and dyeing_stage and big_cone_stage:
                    cur.execute(
                        """SELECT o.id AS dyeing_order_id,o.dyeing_no,o.dyeing_date,
                                  l.id AS source_line_id,l.line_no,l.item_variant_id,
                                  i.item_code,i.item_name,v.variant_code,
                                  COALESCE(v.variant_name,v.variant_code) AS variant_name,
                                  l.batch_id,b.batch_no,l.ownership_type_id,own.code AS ownership_code,
                                  own.name AS ownership_name,l.owner_party_id,p.party_name,
                                  l.location_id,l.process_stage_id,l.unit_id,u.code AS unit_code,
                                  l.quantity_kg AS source_quantity_kg,
                                  COALESCE(l.unit_cost,l.total_cost/NULLIF(l.quantity_kg,0)) AS unit_cost,
                                  COALESCE(a.allocated_kg,0) AS allocated_kg,
                                  l.quantity_kg-COALESCE(a.allocated_kg,0) AS available_kg
                           FROM production.dyeing_output_lines l
                           JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
                           JOIN master.item_variants v ON v.id=l.item_variant_id
                           JOIN master.items i ON i.id=v.item_id
                           JOIN master.ownership_types own ON own.id=l.ownership_type_id
                           JOIN master.units u ON u.id=l.unit_id
                           LEFT JOIN inventory.batches b ON b.id=l.batch_id
                           LEFT JOIN master.parties p ON p.id=l.owner_party_id
                           LEFT JOIN (
                             SELECT ml.source_dyeing_output_line_id,SUM(ml.quantity_kg) AS allocated_kg
                             FROM production.big_cone_material_lines ml
                             JOIN production.big_cone_orders bo ON bo.id=ml.big_cone_order_id
                             WHERE bo.status NOT IN ('CANCELLED','REVERSED')
                             GROUP BY ml.source_dyeing_output_line_id
                           ) a ON a.source_dyeing_output_line_id=l.id
                           WHERE o.company_id=%s AND o.status='POSTED'
                             AND l.output_type='DYED_THREAD'
                             AND l.location_id=%s AND l.process_stage_id=%s
                             AND i.item_code='YARN' AND i.is_active=TRUE AND v.is_active=TRUE
                             AND own.code IN ('OWN','PARTY') AND u.code='KG' AND u.is_active=TRUE
                             AND l.quantity_kg>COALESCE(a.allocated_kg,0)
                           ORDER BY o.dyeing_date DESC,o.id DESC,l.line_no""",
                        (company_id, int(location["location_id"]), int(dyeing_stage["id"])),
                    )
                    sources = [dict(row) for row in cur.fetchall()]
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
    grouped = {}
    for row in sources:
        order_id = int(row["dyeing_order_id"])
        if order_id not in grouped:
            grouped[order_id] = {
                "id": order_id, "dyeing_no": str(row["dyeing_no"]),
                "dyeing_date": row["dyeing_date"], "lines": [],
            }
        row["source_line_id"] = int(row["source_line_id"])
        row["available_kg"] = str(row["available_kg"])
        row["source_quantity_kg"] = str(row["source_quantity_kg"])
        row["unit_cost"] = str(row["unit_cost"]) if row["unit_cost"] is not None else None
        grouped[order_id]["lines"].append(row)
    return {
        "source_orders": list(grouped.values()),
        "departments": departments,
        "machines": machines,
        "raw_store_ready": bool(location),
        "dyeing_stage_ready": bool(dyeing_stage),
        "big_cone_stage_ready": bool(big_cone_stage),
        "has_sources": bool(sources),
        "setup_ready": bool(location and dyeing_stage and big_cone_stage and departments and machines and sources),
    }


def _draft_reconciliation_summary(total_input: Decimal, total_output: Decimal) -> dict[str, Any]:
    """Keep measured wastage separate from the arithmetic input/output difference."""
    return {
        "wastage_quantity_kg": None,
        "unreconciled_difference_kg": str(total_input - total_output),
    }


def create_big_cone_draft(*, company_id: int, user: dict, request: Any,
                          big_cone_date: date, source_dyeing_order_id: int,
                          department_id: int, machine_id: int, remarks: str,
                          lines: list[dict], labour_cost: Any = "0",
                          electricity_cost: Any = "0", machine_cost: Any = "0") -> dict[str, Any]:
    company_id = int(company_id)
    user_id = int(user["id"])
    if not isinstance(big_cone_date, date):
        raise ValueError("Select a valid Big Cone date.")
    try:
        source_order_id = int(source_dyeing_order_id)
        department_id = int(department_id)
        machine_id = int(machine_id)
    except (TypeError, ValueError):
        raise ValueError("Select a valid Dyeing source, department and machine.")
    if min(source_order_id, department_id, machine_id) <= 0:
        raise ValueError("Select a valid Dyeing source, department and machine.")
    remarks = str(remarks or "").strip()
    if len(remarks) > 1000:
        raise ValueError("Remarks cannot exceed 1,000 characters.")
    normalized = normalize_big_cone_lines(lines)
    costs = {
        "labour_cost": _money(labour_cost, "Labour cost"),
        "electricity_cost": _money(electricity_cost, "Electricity cost"),
        "machine_cost": _money(machine_cost, "Machine cost"),
    }
    costs["total_process_cost"] = sum(costs.values(), Decimal("0"))

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM master.process_stages WHERE company_id=%s AND code='DYEING' AND is_active=TRUE FOR SHARE", (company_id,))
                dyeing_stage = cur.fetchone()
                cur.execute("SELECT id FROM master.process_stages WHERE company_id=%s AND code='BIG_CONE' AND is_active=TRUE FOR SHARE", (company_id,))
                big_stage = cur.fetchone()
                cur.execute(
                    """SELECT il.id AS location_id FROM inventory.locations il
                       JOIN core.locations cl ON cl.id=il.core_location_id
                       WHERE cl.company_id=%s AND cl.code='RAW_STORE'
                         AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE
                       FOR SHARE OF il""",
                    (company_id,),
                )
                location = cur.fetchone()
                if not dyeing_stage or not big_stage or not location:
                    raise ValueError("Active DYEING/BIG_CONE stages and the single RAW_STORE location are required.")
                cur.execute("SELECT id FROM core.departments WHERE id=%s AND company_id=%s AND is_active=TRUE FOR SHARE", (department_id, company_id))
                department = cur.fetchone()
                cur.execute("SELECT id,department_id FROM master.machines WHERE id=%s AND company_id=%s AND is_active=TRUE FOR SHARE", (machine_id, company_id))
                machine = cur.fetchone()
                if not department or not machine or int(machine["department_id"] or 0) != department_id:
                    raise ValueError("Select an active machine assigned to the selected active department.")
                cur.execute(
                    """SELECT id,dyeing_no,status FROM production.dyeing_orders
                       WHERE id=%s AND company_id=%s AND status='POSTED' FOR SHARE""",
                    (source_order_id, company_id),
                )
                source_order = cur.fetchone()
                if not source_order:
                    raise ValueError("Selected Dyeing source must be a POSTED order in this company.")

                total_input = Decimal("0")
                total_output = Decimal("0")
                total_input_cones = Decimal("0")
                total_output_cones = Decimal("0")
                material_rows = []
                for line in normalized:
                    cur.execute(
                        """SELECT l.id,l.dyeing_order_id,l.item_variant_id,l.batch_id,l.location_id,
                                  l.ownership_type_id,l.owner_party_id,l.process_stage_id,
                                  l.quantity_kg,l.unit_id,l.output_type,
                                  own.code AS ownership_code,
                                  COALESCE(l.unit_cost,l.total_cost/NULLIF(l.quantity_kg,0)) AS unit_cost
                           FROM production.dyeing_output_lines l
                           JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
                           JOIN master.ownership_types own ON own.id=l.ownership_type_id
                           JOIN master.units u ON u.id=l.unit_id
                           JOIN master.item_variants v ON v.id=l.item_variant_id
                           JOIN master.items i ON i.id=v.item_id
                           WHERE l.id=%s AND l.dyeing_order_id=%s AND o.company_id=%s
                             AND o.status='POSTED' AND l.output_type='DYED_THREAD'
                             AND l.location_id=%s AND l.process_stage_id=%s
                             AND i.item_code='YARN' AND i.is_active=TRUE AND v.is_active=TRUE
                             AND own.code IN ('OWN','PARTY') AND u.code='KG' AND u.is_active=TRUE
                           FOR UPDATE OF l""",
                        (line["source_dyeing_output_line_id"], source_order_id, company_id,
                         int(location["location_id"]), int(dyeing_stage["id"])),
                    )
                    source = cur.fetchone()
                    if not source:
                        raise ValueError(f"Line {line['line_no']}: source must be a posted DYED_THREAD line in the selected Dyeing order, at RAW_STORE/DYEING.")
                    if int(source["unit_id"]) <= 0:
                        raise ValueError(f"Line {line['line_no']}: source unit is invalid.")
                    if source["ownership_code"] == "PARTY" and source["unit_cost"] is None:
                        raise ValueError(f"Line {line['line_no']}: PARTY-owned thread needs its approved locked rate before Big Cone costing.")
                    cur.execute(
                        """SELECT COALESCE(SUM(ml.quantity_kg),0) AS allocated_kg
                           FROM production.big_cone_material_lines ml
                           JOIN production.big_cone_orders bo ON bo.id=ml.big_cone_order_id
                           WHERE ml.source_dyeing_output_line_id=%s
                             AND bo.status NOT IN ('CANCELLED','REVERSED')""",
                        (line["source_dyeing_output_line_id"],),
                    )
                    allocated = Decimal(str(cur.fetchone()["allocated_kg"]))
                    available = Decimal(str(source["quantity_kg"])) - allocated
                    if line["input_quantity_kg"] > available:
                        raise ValueError(f"Line {line['line_no']}: requested input exceeds available Dyeing output ({available} KG).")
                    total_input += line["input_quantity_kg"]
                    total_output += line["output_quantity_kg"]
                    total_input_cones += line["input_cones"]
                    total_output_cones += line["output_cones"]
                    material_rows.append((line, dict(source)))

                prefix = f"BC-{big_cone_date:%Y%m%d}-"
                lock_key = f"big-cone:{company_id}:{big_cone_date.isoformat()}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
                cur.execute(
                    """SELECT COALESCE(MAX(substring(big_cone_no from %s)::integer),0)+1 AS next_no
                       FROM production.big_cone_orders
                       WHERE company_id=%s AND big_cone_no LIKE %s
                         AND substring(big_cone_no from %s) IS NOT NULL""",
                    (f"^{prefix}([0-9]+)$", company_id, prefix + "%", f"^{prefix}([0-9]+)$"),
                )
                big_cone_no = f"{prefix}{int(cur.fetchone()['next_no']):04d}"
                cur.execute(
                    """INSERT INTO production.big_cone_orders
                       (company_id,big_cone_no,big_cone_date,department_id,machine_id,
                        source_dyeing_order_id,status,input_quantity_kg,input_cones,
                        output_quantity_kg,output_cones,wastage_quantity_kg,
                        labour_cost,electricity_cost,machine_cost,total_process_cost,
                        created_by,remarks)
                       VALUES (%s,%s,%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id,big_cone_no,big_cone_date,status,input_quantity_kg,
                                 output_quantity_kg,wastage_quantity_kg,total_process_cost""",
                    (company_id,big_cone_no,big_cone_date,department_id,machine_id,source_order_id,
                     total_input,total_input_cones,total_output,total_output_cones,
                     Decimal("0"),costs["labour_cost"],costs["electricity_cost"],
                     costs["machine_cost"],costs["total_process_cost"],user_id,remarks or None),
                )
                order = dict(cur.fetchone())
                for line, source in material_rows:
                    unit_cost = source["unit_cost"]
                    total_cost = (Decimal(str(unit_cost))*line["input_quantity_kg"]) if unit_cost is not None else None
                    cur.execute(
                        """INSERT INTO production.big_cone_material_lines
                           (big_cone_order_id,line_no,item_variant_id,batch_id,location_id,
                            ownership_type_id,owner_party_id,process_stage_id,quantity_kg,
                            cone_quantity,unit_id,unit_cost,total_cost,source_dyeing_output_line_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,line_no,source_dyeing_output_line_id,quantity_kg,
                                     ownership_type_id,owner_party_id,unit_id""",
                        (order["id"],line["line_no"],source["item_variant_id"],source["batch_id"],
                         source["location_id"],source["ownership_type_id"],source["owner_party_id"],
                         source["process_stage_id"],line["input_quantity_kg"],line["input_cones"],
                         source["unit_id"],unit_cost,total_cost,source["id"]),
                    )
                    material = dict(cur.fetchone())
                    output_total_cost = (Decimal(str(unit_cost))*line["output_quantity_kg"]) if unit_cost is not None else None
                    cur.execute(
                        """INSERT INTO production.big_cone_output_lines
                           (big_cone_order_id,line_no,item_variant_id,batch_id,location_id,
                            ownership_type_id,owner_party_id,process_stage_id,destination_type,
                            quantity_kg,cone_quantity,unit_id,unit_cost,total_cost,source_material_line_id)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,line_no,source_material_line_id,quantity_kg,destination_type""",
                        (order["id"],line["line_no"],source["item_variant_id"],source["batch_id"],
                         source["location_id"],source["ownership_type_id"],source["owner_party_id"],
                         int(big_stage["id"]),line["destination_type"],line["output_quantity_kg"],
                         line["output_cones"],source["unit_id"],unit_cost,output_total_cost,material["id"]),
                    )
                    output = dict(cur.fetchone())
                    write_audit_log(conn,user=user,request=request,action="CREATE",
                        table_name="production.big_cone_material_lines",record_id=material["id"],
                        document_no=big_cone_no,new_values=material,
                        reason="Exact POSTED Dyeing DYED_THREAD source allocated to a Big Cone DRAFT; no stock movement.",
                        module="PRODUCTION")
                    write_audit_log(conn,user=user,request=request,action="CREATE",
                        table_name="production.big_cone_output_lines",record_id=output["id"],
                        document_no=big_cone_no,new_values=output,
                        reason="Big Cone output linked to its exact input line and BIG_CONE stage; no stock movement.",
                        module="PRODUCTION")
                write_audit_log(conn,user=user,request=request,action="CREATE",
                    table_name="production.big_cone_orders",record_id=order["id"],
                    document_no=big_cone_no,new_values={**order,"source_dyeing_no":source_order["dyeing_no"],
                        "line_count":len(material_rows),"process_costs_pkr":{k:str(v) for k,v in costs.items()}},
                    reason="Big Cone header, source lineage, output allocation and process costs saved as DRAFT only; wastage is unmeasured (database-required zero placeholder), and input/output difference remains unreconciled; no inventory posting or stock reservation.",
                    module="PRODUCTION")
    return {"id": int(order["id"]), "big_cone_no": big_cone_no, "status": "DRAFT",
            "line_count": len(material_rows), "input_quantity_kg": str(total_input),
            "output_quantity_kg": str(total_output),
            **_draft_reconciliation_summary(total_input, total_output)}


def get_big_cone_readiness(company_id: int, big_cone_order_id: int) -> dict[str, Any]:
    """Read-only preflight. It never reserves, approves, posts, or changes stock."""
    company_id = int(company_id)
    big_cone_order_id = int(big_cone_order_id)
    if company_id <= 0 or big_cone_order_id <= 0:
        raise ValueError("Select a valid Big Cone document.")

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT id,big_cone_no,big_cone_date,status,source_dyeing_order_id,
                              input_quantity_kg,output_quantity_kg,wastage_quantity_kg,
                              labour_cost,electricity_cost,machine_cost,total_process_cost,
                              approved_at,posted_at
                       FROM production.big_cone_orders
                       WHERE id=%s AND company_id=%s""",
                    (big_cone_order_id, company_id),
                )
                order = cur.fetchone()
                if not order:
                    raise ValueError("Big Cone document was not found in this company.")

                cur.execute(
                    """SELECT ml.id,ml.line_no,ml.quantity_kg AS input_quantity_kg,
                              ml.item_variant_id,ml.batch_id,ml.location_id,
                              ml.ownership_type_id,ml.owner_party_id,ml.process_stage_id,
                              ml.unit_cost,ml.total_cost,
                              own.code AS ownership_code,p.party_name,
                              i.item_code,i.item_name,v.variant_code,b.batch_no,
                              COALESCE(sb.quantity,0) AS current_source_stock_kg,
                              COALESCE((
                                SELECT SUM(other_ml.quantity_kg)
                                FROM production.big_cone_material_lines other_ml
                                JOIN production.big_cone_orders other_order
                                  ON other_order.id=other_ml.big_cone_order_id
                                WHERE other_ml.source_dyeing_output_line_id=ml.source_dyeing_output_line_id
                                  AND other_order.status NOT IN ('CANCELLED','REVERSED')
                                  AND other_order.id<>ml.big_cone_order_id
                              ),0) AS other_big_cone_allocations_kg,
                              ml.source_dyeing_output_line_id
                       FROM production.big_cone_material_lines ml
                       JOIN master.ownership_types own ON own.id=ml.ownership_type_id
                       JOIN master.item_variants v ON v.id=ml.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       LEFT JOIN master.parties p ON p.id=ml.owner_party_id
                       LEFT JOIN inventory.batches b ON b.id=ml.batch_id
                       LEFT JOIN inventory.stock_balances sb
                         ON sb.company_id=%s
                        AND sb.item_variant_id=ml.item_variant_id
                        AND sb.batch_id IS NOT DISTINCT FROM ml.batch_id
                        AND sb.location_id IS NOT DISTINCT FROM ml.location_id
                        AND sb.ownership_type_id=ml.ownership_type_id
                        AND sb.owner_party_id IS NOT DISTINCT FROM ml.owner_party_id
                        AND sb.process_stage_id IS NOT DISTINCT FROM ml.process_stage_id
                       WHERE ml.big_cone_order_id=%s
                       ORDER BY ml.line_no""",
                    (company_id, big_cone_order_id),
                )
                materials = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT ol.id,ol.line_no,ol.quantity_kg,ol.destination_type,
                              ol.unit_cost,ol.total_cost,ol.source_material_line_id,
                              own.code AS ownership_code,p.party_name,
                              i.item_code,i.item_name,v.variant_code,b.batch_no
                       FROM production.big_cone_output_lines ol
                       JOIN master.ownership_types own ON own.id=ol.ownership_type_id
                       JOIN master.item_variants v ON v.id=ol.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       LEFT JOIN master.parties p ON p.id=ol.owner_party_id
                       LEFT JOIN inventory.batches b ON b.id=ol.batch_id
                       WHERE ol.big_cone_order_id=%s
                       ORDER BY ol.line_no""",
                    (big_cone_order_id,),
                )
                outputs = [dict(row) for row in cur.fetchall()]

    input_total = Decimal(str(order["input_quantity_kg"] or 0))
    output_total = Decimal(str(order["output_quantity_kg"] or 0))
    difference = input_total - output_total
    process_cost = Decimal(str(order["total_process_cost"] or 0))
    blockers = []
    if str(order["status"]) != "DRAFT":
        blockers.append(f"Document status is {order['status']}; this screen does not change its status.")
    if not materials or not outputs:
        blockers.append("Material input or output lineage is incomplete.")
    for material in materials:
        input_kg = Decimal(str(material["input_quantity_kg"]))
        stock_kg = Decimal(str(material["current_source_stock_kg"]))
        if stock_kg < input_kg:
            blockers.append(
                f"Input line {material['line_no']}: current DYEING-stage stock is {stock_kg} KG; draft input is {input_kg} KG."
            )
        if material["ownership_code"] == "PARTY" and material["unit_cost"] is None:
            blockers.append(f"Input line {material['line_no']}: PARTY locked unit rate is missing.")
    if difference != 0:
        blockers.append(
            f"{difference} KG remains unreconciled. This is not measured wastage and cannot be treated as a stock return."
        )
    if process_cost > 0:
        blockers.append(
            "Captured labour/electricity/machine process cost has no verified output-line allocation basis yet."
        )
    else:
        blockers.append(
            "No Big Cone process-cost allocation has been verified; confirm actual cost capture before approval."
        )

    return {
        "order": dict(order),
        "materials": materials,
        "outputs": outputs,
        "input_total_kg": str(input_total),
        "output_total_kg": str(output_total),
        "unreconciled_difference_kg": str(difference),
        "measured_wastage_kg": None,
        "process_cost_pkr": str(process_cost),
        "blockers": blockers,
        "ready_for_approval": False,
        "read_only": True,
    }
