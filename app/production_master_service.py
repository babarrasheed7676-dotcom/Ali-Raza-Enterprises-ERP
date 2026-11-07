"""Company-scoped Department and Machine maintenance with audited, soft-deactivation only."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from .db import get_connection
from .audit_service import write_audit_log


def _text(value, label, maximum, *, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{label} is required.")
    if len(value) > maximum:
        raise ValueError(f"{label} cannot exceed {maximum} characters.")
    return value or None


def _active(value):
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "on", "yes"):
        return True
    if value in (0, "0", "false", "False", "off", "no", ""):
        return False
    raise ValueError("Active status must be true or false.")


def _positive_id(value, label, *, optional=False):
    if optional and value in (None, ""):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"Select a valid {label}.")
    if result <= 0:
        raise ValueError(f"Select a valid {label}.")
    return result


def _optional_decimal(value, label):
    if value in (None, ""):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid number.")
    if not number.is_finite() or number < 0 or number >= Decimal("1000000000000"):
        raise ValueError(f"{label} must be zero or greater and within the supported range.")
    if number != number.quantize(Decimal("0.001")):
        raise ValueError(f"{label} supports a maximum of 3 decimal places.")
    return number


def get_production_masters(company_id: int) -> dict:
    company_id = int(company_id)
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT d.id,d.code,d.name,d.description,d.is_active,
                              COUNT(m.id) AS machine_count,
                              COUNT(m.id) FILTER (WHERE m.is_active) AS active_machine_count
                       FROM core.departments d
                       LEFT JOIN master.machines m
                         ON m.department_id=d.id AND m.company_id=d.company_id
                       WHERE d.company_id=%s
                       GROUP BY d.id ORDER BY d.code,d.id""", (company_id,))
                departments = [dict(r) for r in cur.fetchall()]
                cur.execute(
                    """SELECT m.id,m.machine_code,m.machine_name,m.machine_type,
                              m.department_id,d.code AS department_code,d.name AS department_name,
                              m.capacity_quantity,m.capacity_unit_id,u.code AS capacity_unit_code,
                              m.rated_power_kw,m.is_active
                       FROM master.machines m
                       LEFT JOIN core.departments d ON d.id=m.department_id AND d.company_id=m.company_id
                       LEFT JOIN master.units u ON u.id=m.capacity_unit_id
                       WHERE m.company_id=%s ORDER BY m.machine_code,m.id""", (company_id,))
                machines = [dict(r) for r in cur.fetchall()]
                cur.execute("SELECT id,code,name FROM master.units WHERE is_active=TRUE ORDER BY code")
                units = [dict(r) for r in cur.fetchall()]
    return {"departments": departments, "machines": machines, "units": units,
            "active_departments": sum(bool(x["is_active"]) for x in departments),
            "active_machines": sum(bool(x["is_active"]) for x in machines)}


def save_production_master(*, kind: str, payload: dict, company_id: int,
                           user: dict, request, record_id: int | None = None) -> dict:
    kind = str(kind or "").strip().upper()
    if kind not in {"DEPARTMENT", "MACHINE"}:
        raise ValueError("Unsupported production master type.")
    if not isinstance(payload, dict):
        raise ValueError("Master payload must be an object.")
    company_id = int(company_id)
    creating = record_id is None
    rid = None if creating else _positive_id(record_id, "record ID")
    active = _active(payload.get("is_active", True))

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                old = None
                if kind == "DEPARTMENT":
                    if creating:
                        code = _text(payload.get("code"), "Department code", 30).upper()
                        name = _text(payload.get("name"), "Department name", 100)
                        description = _text(payload.get("description"), "Description", 300, required=False)
                        cur.execute(
                            """INSERT INTO core.departments
                               (id,company_id,code,name,description,is_active)
                               VALUES (nextval('core.departments_id_seq'),%s,%s,%s,%s,%s)
                               RETURNING id,code,name,description,is_active""",
                            (company_id,code,name,description,active))
                        saved = dict(cur.fetchone())
                    else:
                        cur.execute("SELECT * FROM core.departments WHERE id=%s AND company_id=%s FOR UPDATE",
                                    (rid,company_id))
                        oldrow = cur.fetchone()
                        if not oldrow:
                            raise ValueError("Department was not found in this company.")
                        old = dict(oldrow)
                        name = _text(payload.get("name",old["name"]), "Department name", 100)
                        description = _text(payload.get("description",old["description"]), "Description", 300, required=False)
                        if old["is_active"] and not active:
                            cur.execute(
                                """SELECT EXISTS(SELECT 1 FROM master.machines
                                                   WHERE department_id=%s AND company_id=%s AND is_active)
                                      OR EXISTS(SELECT 1 FROM production.big_cone_orders
                                                 WHERE department_id=%s AND company_id=%s) AS in_use""",
                                (rid,company_id,rid,company_id))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Department is in use by an active machine or Big Cone history. Deactivate/remove dependencies through their approved workflow first.")
                        cur.execute(
                            """UPDATE core.departments SET name=%s,description=%s,is_active=%s,updated_at=CURRENT_TIMESTAMP
                               WHERE id=%s AND company_id=%s
                               RETURNING id,code,name,description,is_active""",
                            (name,description,active,rid,company_id))
                        saved = dict(cur.fetchone())
                    table = "core.departments"
                    record_id_saved = saved["id"]
                    display = saved["code"]

                else:
                    if creating:
                        code = _text(payload.get("machine_code"), "Machine code", 30).upper()
                        name = _text(payload.get("machine_name"), "Machine name", 100)
                        machine_type = _text(payload.get("machine_type"), "Machine type", 50).upper()
                        department_id = _positive_id(payload.get("department_id"), "department")
                        capacity = _optional_decimal(payload.get("capacity_quantity"), "Capacity")
                        unit_id = _positive_id(payload.get("capacity_unit_id"), "capacity unit", optional=True)
                        power = _optional_decimal(payload.get("rated_power_kw"), "Rated power")
                    else:
                        cur.execute("SELECT * FROM master.machines WHERE id=%s AND company_id=%s FOR UPDATE",
                                    (rid,company_id))
                        oldrow = cur.fetchone()
                        if not oldrow:
                            raise ValueError("Machine was not found in this company.")
                        old = dict(oldrow)
                        name = _text(payload.get("machine_name",old["machine_name"]), "Machine name", 100)
                        machine_type = _text(payload.get("machine_type",old["machine_type"]), "Machine type", 50).upper()
                        department_id = _positive_id(payload.get("department_id",old["department_id"]), "department")
                        capacity = _optional_decimal(payload.get("capacity_quantity",old["capacity_quantity"]), "Capacity")
                        unit_id = _positive_id(payload.get("capacity_unit_id",old["capacity_unit_id"]), "capacity unit", optional=True)
                        power = _optional_decimal(payload.get("rated_power_kw",old["rated_power_kw"]), "Rated power")
                        code = old["machine_code"]
                        if old["is_active"] and not active:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM production.big_cone_orders WHERE machine_id=%s AND company_id=%s) AS in_use",
                                        (rid,company_id))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Machine is referenced by Big Cone history and cannot be deactivated.")
                    if (capacity is None) != (unit_id is None):
                        raise ValueError("Enter both capacity quantity and capacity unit, or leave both blank.")
                    cur.execute("SELECT id FROM core.departments WHERE id=%s AND company_id=%s AND is_active=TRUE FOR SHARE",
                                (department_id,company_id))
                    if not cur.fetchone():
                        raise ValueError("Select an active department belonging to this company.")
                    if unit_id is not None:
                        cur.execute("SELECT id FROM master.units WHERE id=%s AND is_active=TRUE FOR SHARE",(unit_id,))
                        if not cur.fetchone():
                            raise ValueError("Select an active capacity unit.")
                    if creating:
                        cur.execute(
                            """INSERT INTO master.machines
                               (id,company_id,department_id,machine_code,machine_name,machine_type,
                                capacity_quantity,capacity_unit_id,rated_power_kw,is_active)
                               VALUES (nextval('master.machines_id_seq'),%s,%s,%s,%s,%s,%s,%s,%s,%s)
                               RETURNING id,machine_code,machine_name,machine_type,department_id,
                                         capacity_quantity,capacity_unit_id,rated_power_kw,is_active""",
                            (company_id,department_id,code,name,machine_type,capacity,unit_id,power,active))
                    else:
                        cur.execute(
                            """UPDATE master.machines SET department_id=%s,machine_name=%s,machine_type=%s,
                                      capacity_quantity=%s,capacity_unit_id=%s,rated_power_kw=%s,
                                      is_active=%s,updated_at=CURRENT_TIMESTAMP
                               WHERE id=%s AND company_id=%s
                               RETURNING id,machine_code,machine_name,machine_type,department_id,
                                         capacity_quantity,capacity_unit_id,rated_power_kw,is_active""",
                            (department_id,name,machine_type,capacity,unit_id,power,active,rid,company_id))
                    saved = dict(cur.fetchone())
                    table = "master.machines"
                    record_id_saved = saved["id"]
                    display = saved["machine_code"]

                write_audit_log(conn,user=user,request=request,
                    action="CREATE" if creating else "UPDATE",table_name=table,
                    record_id=record_id_saved,document_no=display,
                    old_values=old,new_values=saved,
                    reason=f"{kind.title()} master maintenance; no production or inventory transaction was created.",
                    module="PRODUCTION")
    return saved
