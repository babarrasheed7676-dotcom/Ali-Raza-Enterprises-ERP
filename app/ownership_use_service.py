"""Separate PARTY-stock use request and approval workflow helpers."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .audit_service import write_audit_log
from .configuration_runtime_service import resolve_ownership_policy_snapshot


MODULE_TABLES = {
    "DYEING": ("production.dyeing_consumption_lines", "quantity", "DYEING-OWNERSHIP"),
    "PACKING": ("production.packing_source_allocations", "quantity_pieces", "NALKI-OWNERSHIP"),
}


def _positive_rate(value: Any) -> Decimal:
    try:
        rate = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Party rate must be a valid PKR amount.")
    if not rate.is_finite() or rate <= 0 or rate >= Decimal("1000000000000"):
        raise ValueError("Party rate must be positive and within the supported range.")
    if rate != rate.quantize(Decimal("0.000001")):
        raise ValueError("Party rate supports a maximum of 6 decimal places.")
    return rate


def _validate_request_unit_id(requested_unit_id: int | None, line_unit_id: int | None) -> None:
    requested = int(requested_unit_id) if requested_unit_id is not None else None
    source = int(line_unit_id) if line_unit_id is not None else None
    if requested != source:
        raise ValueError("Requested rate unit must exactly match the source DRAFT line unit.")


def create_ownership_use_request(
    cur, *, company_id: int, module: str, target_line_id: int,
    owner_party_id: int, requested_quantity: Any, unit_id: int | None,
    requested_unit_rate: Any, reason: str, requester_id: int,
    effective_on: date, user: dict, request: Any,
) -> dict:
    """Create a PENDING request and attach it to an existing PARTY DRAFT line."""
    if int(user.get("id", 0)) != int(requester_id) or int(user.get("company_id", 0)) != int(company_id):
        raise ValueError("PARTY-use requester/company context is invalid.")
    module = str(module or "").strip().upper()
    if module not in MODULE_TABLES:
        raise ValueError("Ownership-use module must be DYEING or PACKING.")
    table, quantity_column, policy_key = MODULE_TABLES[module]
    try:
        quantity = Decimal(str(requested_quantity).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Requested PARTY quantity must be numeric.")
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("Requested PARTY quantity must be positive.")
    if quantity != quantity.quantize(Decimal("0.000001")):
        raise ValueError("Requested PARTY quantity supports a maximum of 6 decimal places.")
    rate = _positive_rate(requested_unit_rate)
    reason = str(reason or "").strip()
    if not 5 <= len(reason) <= 1000:
        raise ValueError("Explain the PARTY stock requirement in 5 to 1,000 characters.")

    snapshot = resolve_ownership_policy_snapshot(
        cur, company_id=int(company_id), effective_on=effective_on, config_key=policy_key
    )
    if "PARTY" not in snapshot["payload"].get("allowed_owners", []):
        raise ValueError("The approved ownership policy does not allow PARTY stock.")

    cur.execute(
        f"""SELECT l.id,l.owner_party_id,l.ownership_type_id,l.{quantity_column} AS quantity,
                   {"l.unit_id" if module == "DYEING" else "NULL::bigint"} AS line_unit_id,
                   o.status,o.company_id,o.{"dyeing_date" if module == "DYEING" else "packing_date"} AS document_date
            FROM {table} l
            JOIN production.{"dyeing_orders" if module == "DYEING" else "packing_orders"} o
              ON o.id=l.{"dyeing_order_id" if module == "DYEING" else "packing_order_id"}
            WHERE l.id=%s FOR UPDATE OF l,o""",
        (int(target_line_id),),
    )
    line = cur.fetchone()
    if not line or line["document_date"] != effective_on:
        raise ValueError("Ownership policy date must match the source document date.")
    _validate_request_unit_id(unit_id, line["line_unit_id"])
    if (int(line["company_id"]) != int(company_id)
        or line["status"] != "DRAFT" or int(line["ownership_type_id"]) != 2
        or int(line["owner_party_id"] or 0) != int(owner_party_id)
        or Decimal(str(line["quantity"])) != quantity):
        raise ValueError("Request must exactly match the same-company DRAFT PARTY line, owner and quantity.")

    cur.execute(
        """INSERT INTO production.ownership_use_requests
           (company_id,use_module,target_line_id,ownership_policy_version_id,
            owner_party_id,requested_quantity,unit_id,currency_code,
            requested_unit_rate,status,request_reason,requested_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'PKR',%s,'PENDING',%s,%s)
           RETURNING id,status,ownership_policy_version_id,requested_unit_rate""",
        (int(company_id), module, int(target_line_id),
         snapshot["configuration_version_id"], int(owner_party_id),
         quantity, int(unit_id) if unit_id is not None else None,
         rate, reason, int(requester_id)),
    )
    saved = dict(cur.fetchone())
    cur.execute(
        f"UPDATE {table} SET ownership_use_request_id=%s WHERE id=%s",
        (int(saved["id"]), int(target_line_id)),
    )
    write_audit_log(
        cur.connection, user=user, request=request, action="CREATE_PARTY_USE_REQUEST",
        table_name="production.ownership_use_requests", record_id=saved["id"],
        new_values={**saved, "use_module": module, "target_line_id": int(target_line_id),
                    "owner_party_id": int(owner_party_id), "requested_quantity": str(quantity),
                    "currency_code": "PKR", "status": "PENDING"},
        reason="Separate PARTY-stock use request; no stock movement or posting.",
        module=module,
    )
    return saved


def build_ownership_cost_snapshot(row: dict, *, snapshot_at: Any) -> dict:
    """Create a deterministic cost snapshot from an approved, locked PARTY-use request."""
    if row.get("status") != "APPROVED" or row.get("locked_unit_rate") is None:
        raise ValueError("Only an approved request with a locked rate can create a cost snapshot.")
    quantity = Decimal(str(row["requested_quantity"]))
    rate = _positive_rate(row["locked_unit_rate"])
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("Approved PARTY quantity must be positive.")
    total = (quantity * rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return {
        "schema_version": 1,
        "module": str(row["use_module"]),
        "request_id": int(row["id"]),
        "company_id": int(row["company_id"]),
        "target_line_id": int(row["target_line_id"]),
        "ownership_policy_version_id": int(row["ownership_policy_version_id"]),
        "owner_party_id": int(row["owner_party_id"]),
        "quantity": str(quantity),
        "unit_id": int(row["unit_id"]) if row.get("unit_id") is not None else None,
        "currency_code": str(row["currency_code"]),
        "locked_unit_rate": str(rate),
        "total_cost": str(total),
        "requested_by": int(row["requested_by"]),
        "approved_by": int(row["decided_by"]),
        "approved_at": row["decided_at"].isoformat() if row.get("decided_at") else None,
        "snapshot_at": snapshot_at.isoformat() if hasattr(snapshot_at, "isoformat") else str(snapshot_at),
    }


def persist_ownership_cost_snapshot(cur, *, request_id: int, company_id: int) -> dict:
    """Pin the approved rate and total onto its exact DRAFT consumption/source line."""
    cur.execute(
        """SELECT r.*,CURRENT_TIMESTAMP AS snapshot_at
           FROM production.ownership_use_requests r
           WHERE r.id=%s AND r.company_id=%s FOR UPDATE""",
        (int(request_id), int(company_id)),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("Approved PARTY-use request was not found in this company.")
    snapshot = build_ownership_cost_snapshot(dict(row), snapshot_at=row["snapshot_at"])
    import json
    table = "production.dyeing_consumption_lines" if row["use_module"] == "DYEING" else "production.packing_source_allocations"
    qty_col = "quantity" if row["use_module"] == "DYEING" else "quantity_pieces"
    order_fk = "dyeing_order_id" if row["use_module"] == "DYEING" else "packing_order_id"
    order_table = "dyeing_orders" if row["use_module"] == "DYEING" else "packing_orders"
    cur.execute(
        f"""SELECT l.id,l.{qty_col} AS quantity,l.owner_party_id,l.ownership_type_id,
                   l.ownership_use_request_id,o.status,o.company_id
            FROM {table} l JOIN production.{order_table} o ON o.id=l.{order_fk}
            WHERE l.id=%s FOR UPDATE OF l,o""",
        (int(row["target_line_id"]),),
    )
    line = cur.fetchone()
    if (not line or line["status"] != "DRAFT" or int(line["company_id"]) != int(company_id)
        or int(line["ownership_type_id"]) != 2 or int(line["owner_party_id"] or 0) != int(row["owner_party_id"])
        or int(line["ownership_use_request_id"] or 0) != int(request_id)
        or Decimal(str(line["quantity"])) != Decimal(str(row["requested_quantity"]))):
        raise ValueError("Approved PARTY-use request no longer matches its exact DRAFT source line.")
    total = Decimal(snapshot["total_cost"])
    if row["use_module"] == "DYEING":
        cur.execute(
            """UPDATE production.dyeing_consumption_lines
               SET ownership_policy_version_id=%s,ownership_locked_unit_rate=%s,
                   ownership_cost_total=%s,ownership_cost_snapshot=%s::jsonb,
                   ownership_cost_snapshotted_at=%s,unit_cost=%s,total_cost=%s
               WHERE id=%s AND ownership_cost_snapshot IS NULL""",
            (int(row["ownership_policy_version_id"]),row["locked_unit_rate"],total,
             json.dumps(snapshot),row["snapshot_at"],row["locked_unit_rate"],total,int(row["target_line_id"])),
        )
    else:
        cur.execute(
            """UPDATE production.packing_source_allocations
               SET ownership_policy_version_id=%s,ownership_locked_unit_rate=%s,
                   ownership_cost_total=%s,ownership_cost_snapshot=%s::jsonb,
                   ownership_cost_snapshotted_at=%s
               WHERE id=%s AND ownership_cost_snapshot IS NULL""",
            (int(row["ownership_policy_version_id"]),row["locked_unit_rate"],total,
             json.dumps(snapshot),row["snapshot_at"],int(row["target_line_id"])),
        )
    if cur.rowcount != 1:
        raise ValueError("PARTY cost snapshot already exists or could not be pinned.")
    return snapshot


def decide_ownership_use_request(
    cur, *, company_id: int, request_id: int, approver_id: int,
    approve: bool, decision_note: str, user: dict, request: Any,
) -> dict:
    """Approve/reject a pending PARTY-use request; approval locks the requested rate."""
    if int(user.get("id", 0)) != int(approver_id) or int(user.get("company_id", 0)) != int(company_id):
        raise ValueError("PARTY-use approver/company context is invalid.")
    note = str(decision_note or "").strip()
    if not 5 <= len(note) <= 1000:
        raise ValueError("Approval/rejection note must contain 5 to 1,000 characters.")
    cur.execute(
        """SELECT * FROM production.ownership_use_requests
           WHERE id=%s AND company_id=%s FOR UPDATE""",
        (int(request_id), int(company_id)),
    )
    row = cur.fetchone()
    if not row or row["status"] != "PENDING":
        raise ValueError("Only a pending PARTY-use request can be decided.")
    if int(row["requested_by"]) == int(approver_id):
        raise ValueError("The requester cannot approve their own PARTY-stock use request.")
    new_status = "APPROVED" if approve else "REJECTED"
    locked_rate = row["requested_unit_rate"] if approve else None
    cur.execute(
        """UPDATE production.ownership_use_requests
           SET status=%s,locked_unit_rate=%s,decided_by=%s,
               decided_at=CURRENT_TIMESTAMP,decision_note=%s,updated_at=CURRENT_TIMESTAMP
           WHERE id=%s
           RETURNING id,status,locked_unit_rate,decided_by,decided_at""",
        (new_status, locked_rate, int(approver_id), note, int(request_id)),
    )
    saved = dict(cur.fetchone())
    if new_status == "APPROVED":
        saved["cost_snapshot"] = persist_ownership_cost_snapshot(
            cur, request_id=int(request_id), company_id=int(company_id)
        )
    write_audit_log(
        cur.connection, user=user, request=request, action=f"DECIDE_PARTY_USE_{new_status}",
        table_name="production.ownership_use_requests", record_id=saved["id"],
        new_values=saved, reason=note, module=str(row["use_module"]),
    )
    return saved


def list_ownership_use_requests(cur, *, company_id: int, modules: list[str], limit: int = 200) -> list[dict]:
    """Read-only, company-scoped PARTY-use queue for authorized modules."""
    allowed = sorted({str(x).upper() for x in modules} & set(MODULE_TABLES))
    if not allowed:
        return []
    cur.execute(
        """SELECT r.id,r.use_module,r.target_line_id,r.status,r.owner_party_id,
                  p.party_name,p.party_code,r.requested_quantity,r.unit_id,
                  u.code AS unit_code,u.name AS unit_name,r.currency_code,
                  r.requested_unit_rate,r.locked_unit_rate,r.request_reason,
                  r.requested_by,ru.full_name AS requester_name,
                  r.decided_by,du.full_name AS approver_name,r.decision_note,
                  r.created_at,r.decided_at,r.ownership_policy_version_id,
                  cv.version_no AS policy_version
           FROM production.ownership_use_requests r
           JOIN master.parties p ON p.id=r.owner_party_id AND p.company_id=r.company_id
           LEFT JOIN master.units u ON u.id=r.unit_id
           JOIN core.users ru ON ru.id=r.requested_by
           LEFT JOIN core.users du ON du.id=r.decided_by
           JOIN configuration.config_versions cv ON cv.id=r.ownership_policy_version_id
           WHERE r.company_id=%s AND r.use_module=ANY(%s)
           ORDER BY CASE r.status WHEN 'PENDING' THEN 0 ELSE 1 END,
                    r.created_at DESC,r.id DESC
           LIMIT %s""",
        (int(company_id), allowed, max(1,min(int(limit),500))),
    )
    return [dict(row) for row in cur.fetchall()]


def list_party_draft_lines(cur, *, company_id: int, modules: list[str]) -> list[dict]:
    """Find existing same-company DRAFT PARTY lines eligible to request separately."""
    allowed = sorted({str(x).upper() for x in modules} & set(MODULE_TABLES))
    rows = []
    if "DYEING" in allowed:
        cur.execute(
            """SELECT 'DYEING' AS use_module,l.id AS target_line_id,
                      o.dyeing_date AS effective_on,l.owner_party_id,p.party_name,
                      l.quantity AS requested_quantity,l.unit_id,u.code AS unit_code,
                      i.item_name AS source_description,o.dyeing_no AS source_document
               FROM production.dyeing_consumption_lines l
               JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
               JOIN master.parties p ON p.id=l.owner_party_id AND p.company_id=o.company_id
               JOIN master.units u ON u.id=l.unit_id
               JOIN master.item_variants v ON v.id=l.item_variant_id
               JOIN master.items i ON i.id=v.item_id
               WHERE o.company_id=%s AND o.status='DRAFT'
                 AND l.ownership_type_id=2 AND l.owner_party_id IS NOT NULL
               ORDER BY o.dyeing_date DESC,o.id DESC,l.line_no""",
            (int(company_id),),
        )
        rows.extend(dict(x) for x in cur.fetchall())
    if "PACKING" in allowed:
        cur.execute(
            """SELECT 'PACKING' AS use_module,a.id AS target_line_id,
                      o.packing_date AS effective_on,a.owner_party_id,p.party_name,
                      a.quantity_pieces AS requested_quantity,NULL::bigint AS unit_id,
                      'PCS'::text AS unit_code,i.item_name AS source_description,
                      o.packing_no AS source_document
               FROM production.packing_source_allocations a
               JOIN production.packing_orders o ON o.id=a.packing_order_id
               JOIN master.parties p ON p.id=a.owner_party_id AND p.company_id=o.company_id
               JOIN master.item_variants v ON v.id=a.item_variant_id
               JOIN master.items i ON i.id=v.item_id
               WHERE o.company_id=%s AND o.status='DRAFT'
                 AND a.ownership_type_id=2 AND a.owner_party_id IS NOT NULL
               ORDER BY o.packing_date DESC,o.id DESC,a.id""",
            (int(company_id),),
        )
        rows.extend(dict(x) for x in cur.fetchall())
    rows = sorted(rows,key=lambda x:(x["effective_on"],x["source_document"],x["target_line_id"]),reverse=True)
    for row in rows:
        row["effective_on"] = row["effective_on"].isoformat() if row["effective_on"] else None
        row["requested_quantity"] = str(row["requested_quantity"])
        row["target_line_id"] = int(row["target_line_id"])
        row["owner_party_id"] = int(row["owner_party_id"])
        row["unit_id"] = int(row["unit_id"]) if row["unit_id"] is not None else None
    return rows
