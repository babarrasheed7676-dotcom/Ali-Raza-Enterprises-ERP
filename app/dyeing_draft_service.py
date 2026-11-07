"""Safe DRAFT-only dyeing consumption workflow; no inventory posting."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from .db import get_connection
from .audit_service import write_audit_log
from psycopg.types.json import Jsonb
from .dyeing_conversion_service import build_dyeing_unit_conversion_snapshot


ALLOWED_DYE_CATEGORIES = {"POLY_DYE", "COTTON_DYE"}
ALLOWED_CHEMICAL_CATEGORIES = {"POLY_CHEM", "COTTON_CHEM", "COMMON_CHEM"}


def _positive_kg(value: Any, label: str) -> Decimal:
    try:
        quantity = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{label} must be a valid KG quantity.")
    if not quantity.is_finite() or quantity <= 0 or quantity >= Decimal("1000000000000"):
        raise ValueError(f"{label} must be positive and within the supported range.")
    if quantity != quantity.quantize(Decimal("0.001")):
        raise ValueError(f"{label} supports a maximum of 3 decimal places because KG stock is stored to 0.001.")
    return quantity


PROCESS_COST_FIELDS = (
    "labour_cost", "machine_cost", "electricity_cost",
    "water_cost", "boiler_fuel_cost", "drying_cost",
)


def normalize_dyeing_process_costs(values: dict | None) -> dict[str, Decimal]:
    """Normalize actual Dyeing salary/overhead costs in company currency (PKR)."""
    values = values or {}
    if not isinstance(values, dict):
        raise ValueError("Dyeing process costs must be a field/value object.")
    normalized = {}
    for field in PROCESS_COST_FIELDS:
        try:
            amount = Decimal(str(values.get(field, "0") or "0").strip())
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"{field.replace('_', ' ').title()} must be a valid PKR amount.")
        if not amount.is_finite() or amount < 0 or amount >= Decimal("100000000000000"):
            raise ValueError(f"{field.replace('_', ' ').title()} must be non-negative and within numeric(20,6).")
        try:
            rounded = amount.quantize(Decimal("0.000001"))
        except InvalidOperation:
            raise ValueError(f"{field.replace('_', ' ').title()} exceeds supported PKR precision.")
        if amount != rounded:
            raise ValueError(f"{field.replace('_', ' ').title()} supports a maximum of 6 decimal places.")
        normalized[field] = amount
    total = sum(normalized.values(), Decimal("0"))
    if total >= Decimal("100000000000000"):
        raise ValueError("Total Dyeing process cost exceeds the supported numeric(20,6) range.")
    normalized["total_process_cost"] = total
    return normalized


def normalize_dyeing_yarn_io(material_lines: list[dict] | None,
                             output_lines: list[dict] | None) -> tuple[list[dict], list[dict]]:
    """Validate raw-yarn inputs and DYED_THREAD outputs without any database writes."""
    if not isinstance(material_lines, list) or not 1 <= len(material_lines) <= 100:
        raise ValueError("Add between 1 and 100 raw-yarn input lines.")
    if not isinstance(output_lines, list) or not 1 <= len(output_lines) <= 100:
        raise ValueError("Add between 1 and 100 DYED_THREAD output lines.")

    normalized_inputs = []
    for index, line in enumerate(material_lines, start=1):
        try:
            variant_id = int(line.get("item_variant_id"))
        except (TypeError, ValueError):
            raise ValueError(f"Yarn input {index}: select a valid YARN item variant.")
        if variant_id <= 0:
            raise ValueError(f"Yarn input {index}: select a valid YARN item variant.")
        batch_text = str(line.get("batch_id") or "").strip()
        try:
            batch_id = int(batch_text) if batch_text else None
        except ValueError:
            raise ValueError(f"Yarn input {index}: select a valid batch.")
        if batch_id is not None and batch_id <= 0:
            raise ValueError(f"Yarn input {index}: select a valid batch.")
        quantity = _positive_kg(line.get("quantity_kg"), f"Yarn input {index} quantity")
        notes = str(line.get("notes") or "").strip()
        if len(notes) > 200:
            raise ValueError(f"Yarn input {index}: notes cannot exceed 200 characters.")
        normalized_inputs.append({
            "line_no": index, "item_variant_id": variant_id,
            "batch_id": batch_id, "quantity_kg": quantity,
            "notes": notes or None,
        })

    input_by_line = {row["line_no"]: row for row in normalized_inputs}
    normalized_outputs = []
    source_allocations: dict[int, Decimal] = {}
    for index, line in enumerate(output_lines, start=1):
        try:
            source_line_no = int(line.get("source_line_no"))
            shade_id = int(line.get("actual_shade_id"))
        except (TypeError, ValueError):
            raise ValueError(f"DYED_THREAD output {index}: select a source yarn line and an active shade.")
        if source_line_no not in input_by_line or shade_id <= 0:
            raise ValueError(f"DYED_THREAD output {index}: source yarn line or shade is invalid.")
        source_quantity = _positive_kg(
            line.get("source_quantity_kg"), f"DYED_THREAD output {index} consumed-yarn quantity"
        )
        output_quantity = _positive_kg(
            line.get("quantity_kg"), f"DYED_THREAD output {index} output quantity"
        )
        notes = str(line.get("notes") or "").strip()
        if len(notes) > 200:
            raise ValueError(f"DYED_THREAD output {index}: notes cannot exceed 200 characters.")
        source_allocations[source_line_no] = source_allocations.get(source_line_no, Decimal("0")) + source_quantity
        normalized_outputs.append({
            "line_no": index, "source_line_no": source_line_no,
            "source_quantity_kg": source_quantity,
            "quantity_kg": output_quantity, "actual_shade_id": shade_id,
            "notes": notes or None,
        })

    for line_no, allocated in source_allocations.items():
        source_quantity = input_by_line[line_no]["quantity_kg"]
        if allocated > source_quantity:
            raise ValueError(
                f"DYED_THREAD outputs consume {allocated} KG from yarn input line {line_no}, "
                f"but only {source_quantity} KG was entered."
            )
    return normalized_inputs, normalized_outputs



def validate_dyeing_party_use_authorization(ownership_code: str) -> None:
    """Allow PARTY only in DRAFT capture; status gate requires separate approval before advance."""
    if str(ownership_code or "").strip().upper() not in {"OWN", "PARTY"}:
        raise ValueError("Dyeing material ownership must be OWN or PARTY.")


def get_dyeing_draft_form_data(company_id: int) -> dict[str, Any]:
    """Return active dye/chemical variants, weight units and the single raw store."""
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT v.id AS item_variant_id, i.id AS item_id,
                              i.item_code, i.item_name, v.variant_code,
                              COALESCE(v.variant_name, i.item_name) AS variant_name,
                              c.code AS category_code, c.name AS category_name,
                              bu.code AS base_unit_code,i.track_batch
                       FROM master.item_variants v
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.item_categories c ON c.id=i.item_category_id
                       JOIN master.item_categories parent ON parent.id=c.parent_category_id
                       JOIN master.units bu ON bu.id=i.base_unit_id
                       WHERE i.company_id=%s AND i.is_active=TRUE AND v.is_active=TRUE
                         AND c.is_active=TRUE AND parent.code='DYE_CHEM'
                         AND c.code = ANY(%s)
                       ORDER BY c.name,i.item_name,v.variant_code""",
                    (int(company_id), sorted(ALLOWED_DYE_CATEGORIES | ALLOWED_CHEMICAL_CATEGORIES)),
                )
                items = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    "SELECT id,code,name,decimal_places FROM master.units "
                    "WHERE is_active=TRUE AND unit_type='WEIGHT' ORDER BY decimal_places,code"
                )
                units = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    "SELECT id,code,name,is_company_owned FROM master.ownership_types "
                    "WHERE is_active=TRUE ORDER BY id"
                )
                ownership_types = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    "SELECT id,party_code,party_name FROM master.parties "
                    "WHERE company_id=%s AND is_active=TRUE ORDER BY party_name",
                    (int(company_id),),
                )
                parties = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT il.id AS inventory_location_id, cl.code, cl.name
                       FROM inventory.locations il
                       JOIN core.locations cl ON cl.id=il.core_location_id
                       WHERE cl.company_id=%s AND cl.code='RAW_STORE'
                         AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE""",
                    (int(company_id),),
                )
                location = cur.fetchone()
                if not location:
                    raise ValueError("The verified Raw Material Store inventory location is not configured.")
                cur.execute(
                    """SELECT id FROM master.process_stages
                       WHERE company_id=%s AND code='PURCHASE' AND is_active=TRUE""",
                    (int(company_id),),
                )
                purchase_stage = cur.fetchone()
                cur.execute(
                    """SELECT id FROM master.ownership_types
                       WHERE code='OWN' AND is_active=TRUE"""
                )
                own_type = cur.fetchone()
                if not purchase_stage or not own_type:
                    raise ValueError("Active PURCHASE stage and OWN ownership masters are required for raw yarn.")
                cur.execute(
                    """SELECT v.id AS item_variant_id, i.item_code, i.item_name,
                              v.variant_code, COALESCE(v.variant_name,v.variant_code) AS variant_name,
                              bu.code AS base_unit_code,
                              COALESCE(SUM(sb.quantity),0) AS available_quantity_kg
                       FROM master.item_variants v
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.item_categories c ON c.id=i.item_category_id
                       JOIN master.units bu ON bu.id=i.base_unit_id
                       LEFT JOIN inventory.stock_balances sb
                         ON sb.company_id=i.company_id AND sb.item_variant_id=v.id
                        AND sb.location_id=%s AND sb.process_stage_id=%s
                        AND sb.ownership_type_id=%s AND sb.owner_party_id IS NULL
                       WHERE i.company_id=%s AND i.is_active=TRUE AND v.is_active=TRUE
                         AND i.is_stock_item=TRUE AND c.code='YARN'
                         AND bu.code='KG' AND bu.unit_type='WEIGHT'
                         AND v.brand_id IS NULL AND v.shade_id IS NULL
                       GROUP BY v.id,i.item_code,i.item_name,v.variant_code,v.variant_name,bu.code
                       ORDER BY i.item_name,v.variant_code""",
                    (int(location["inventory_location_id"]), int(purchase_stage["id"]),
                     int(own_type["id"]), int(company_id)),
                )
                raw_yarn_items = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT s.id AS shade_id,s.brand_id,b.code AS brand_code,
                              b.name AS brand_name,s.shade_code,s.shade_name
                       FROM master.shades s
                       JOIN master.brands b ON b.id=s.brand_id
                       WHERE s.is_active=TRUE AND b.is_active=TRUE
                       ORDER BY b.id,
                         CASE WHEN s.shade_code ~ '^[0-9]+$' THEN s.shade_code::integer ELSE 999999 END,
                         s.shade_code""",
                )
                shades = [dict(row) for row in cur.fetchall()]
                shade_groups = []
                for brand_id in sorted({int(row["brand_id"]) for row in shades}):
                    group_rows = [row for row in shades if int(row["brand_id"]) == brand_id]
                    if group_rows:
                        shade_groups.append({
                            "brand_id": brand_id,
                            "brand_name": group_rows[0]["brand_name"],
                            "shades": group_rows,
                        })
                cur.execute(
                    """SELECT b.id AS batch_id,b.batch_no,b.item_variant_id,v.variant_code
                       FROM inventory.batches b
                       JOIN master.item_variants v ON v.id=b.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       JOIN inventory.stock_balances sb
                         ON sb.company_id=b.company_id AND sb.item_variant_id=b.item_variant_id
                        AND sb.batch_id=b.id AND sb.location_id=%s
                        AND sb.process_stage_id=%s AND sb.ownership_type_id=%s
                        AND sb.owner_party_id IS NULL AND sb.quantity>0
                       WHERE b.company_id=%s AND i.item_code='YARN'
                         AND b.process_stage_id=%s AND b.ownership_type_id=%s
                         AND b.owner_party_id IS NULL AND COALESCE(b.current_quantity,0)>0
                       ORDER BY b.batch_no""",
                    (int(location["inventory_location_id"]), int(purchase_stage["id"]),
                     int(own_type["id"]), int(company_id), int(purchase_stage["id"]),
                     int(own_type["id"])),
                )
                yarn_batches = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT b.id AS batch_id,b.batch_no,b.item_variant_id,v.variant_code,
                              b.ownership_type_id,own.code AS ownership_code,b.owner_party_id,
                              p.party_name,sb.quantity AS available_quantity
                       FROM inventory.batches b
                       JOIN master.item_variants v ON v.id=b.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.item_categories c ON c.id=i.item_category_id
                       JOIN master.item_categories parent ON parent.id=c.parent_category_id
                       JOIN master.ownership_types own ON own.id=b.ownership_type_id
                       LEFT JOIN master.parties p ON p.id=b.owner_party_id
                       JOIN inventory.stock_balances sb
                         ON sb.company_id=b.company_id AND sb.item_variant_id=b.item_variant_id
                        AND sb.batch_id=b.id AND sb.location_id=%s
                        AND sb.process_stage_id=%s
                        AND sb.ownership_type_id=b.ownership_type_id
                        AND sb.owner_party_id IS NOT DISTINCT FROM b.owner_party_id
                        AND sb.quantity>0
                       WHERE b.company_id=%s AND parent.code='DYE_CHEM'
                         AND b.process_stage_id=%s
                         AND COALESCE(b.current_quantity,0)>0
                       ORDER BY i.item_name,b.batch_no""",
                    (int(location["inventory_location_id"]),int(purchase_stage["id"]),
                     int(company_id),int(purchase_stage["id"])),
                )
                chemical_batches = [dict(row) for row in cur.fetchall()]
    return {
        "items": items,
        "units": units,
        "ownership_types": ownership_types,
        "parties": parties,
        "raw_store": dict(location),
        "raw_yarn_items": raw_yarn_items,
        "shades": shades,
        "shade_groups": shade_groups,
        "yarn_batches": yarn_batches,
        "chemical_batches": chemical_batches,
    }


def create_dyeing_draft(*, company_id: int, user: dict, request: Any,
                        dyeing_date: date, remarks: str, lines: list[dict],
                        material_lines: list[dict] | None = None,
                        output_lines: list[dict] | None = None,
                        process_costs: dict | None = None) -> dict[str, Any]:
    """Save a dyeing order and material lines as DRAFT only; never touch stock."""
    company_id = int(company_id)
    user_id = int(user["id"])
    if not isinstance(dyeing_date, date):
        raise ValueError("Select a valid dyeing date.")
    remarks = str(remarks or "").strip()
    if len(remarks) > 1000:
        raise ValueError("Remarks cannot exceed 1,000 characters.")
    if lines is None:
        lines = []
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("Add between 1 and 100 dye/chemical consumption lines.")
    normalized_materials, normalized_outputs = normalize_dyeing_yarn_io(material_lines, output_lines)
    normalized_costs = normalize_dyeing_process_costs(process_costs)

    normalized = []
    for index, line in enumerate(lines, start=1):
        try:
            quantity = Decimal(str(line.get("quantity", "")).strip())
        except (InvalidOperation, TypeError):
            raise ValueError(f"Line {index}: enter a valid quantity.")
        if not quantity.is_finite() or quantity <= 0:
            raise ValueError(f"Line {index}: quantity must be greater than zero.")
        if quantity >= Decimal("1000000000000"):
            raise ValueError(f"Line {index}: quantity exceeds the supported numeric(18,6) range.")
        try:
            rounded_check = quantity.quantize(Decimal("0.000001"))
        except InvalidOperation:
            raise ValueError(f"Line {index}: quantity exceeds the supported numeric(18,6) range.")
        if quantity != rounded_check:
            raise ValueError(f"Line {index}: quantity supports a maximum of 6 decimal places.")
        try:
            variant_id = int(line.get("item_variant_id"))
            unit_id = int(line.get("unit_id"))
            ownership_type_id = int(line.get("ownership_type_id", 1))
        except (TypeError, ValueError):
            raise ValueError(f"Line {index}: select a valid item, unit and ownership type.")
        party_text = str(line.get("owner_party_id") or "").strip()
        try:
            owner_party_id = int(party_text) if party_text else None
        except ValueError:
            raise ValueError(f"Line {index}: select a valid owner party.")
        batch_text = str(line.get("batch_id") or "").strip()
        try:
            batch_id = int(batch_text) if batch_text else None
        except ValueError:
            raise ValueError(f"Line {index}: select a valid batch.")
        if batch_id is not None and batch_id <= 0:
            raise ValueError(f"Line {index}: select a valid batch.")
        try:
            source_line_no = int(line.get("source_line_no"))
        except (TypeError, ValueError):
            raise ValueError(f"Line {index}: select the raw-Yarn input line this material is used on.")
        valid_source_lines = {int(x["line_no"]) for x in normalized_materials}
        if source_line_no not in valid_source_lines:
            raise ValueError(f"Line {index}: selected raw-Yarn input line is not part of this Dyeing order.")
        notes = str(line.get("notes") or "").strip()
        if len(notes) > 200:
            raise ValueError(f"Line {index}: notes cannot exceed 200 characters.")
        normalized.append({
            "line_no": index, "quantity": quantity, "item_variant_id": variant_id,
            "unit_id": unit_id, "ownership_type_id": ownership_type_id,
            "owner_party_id": owner_party_id, "batch_id": batch_id,
            "source_line_no": source_line_no, "notes": notes or None,
        })

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM master.process_stages WHERE company_id=%s AND code='DYEING' AND is_active=TRUE FOR SHARE", (company_id,))
                stage = cur.fetchone()
                if not stage:
                    raise ValueError("Active DYEING process stage is not configured.")
                cur.execute(
                    """SELECT il.id AS location_id
                       FROM inventory.locations il JOIN core.locations cl ON cl.id=il.core_location_id
                       WHERE cl.company_id=%s AND cl.code='RAW_STORE'
                         AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE
                       FOR SHARE OF il""", (company_id,)
                )
                location = cur.fetchone()
                if not location:
                    raise ValueError("The single Raw Material Store is not configured for stock.")
                location_id = int(location["location_id"])
                cur.execute(
                    "SELECT id FROM master.process_stages WHERE company_id=%s AND code='PURCHASE' AND is_active=TRUE FOR SHARE",
                    (company_id,),
                )
                purchase_stage = cur.fetchone()
                if not purchase_stage:
                    raise ValueError("Active PURCHASE process stage is not configured.")
                purchase_stage_id = int(purchase_stage["id"])
                cur.execute(
                    "SELECT id FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE FOR SHARE"
                )
                own_row = cur.fetchone()
                if not own_row:
                    raise ValueError("Active OWN ownership type is not configured.")
                own_type_id = int(own_row["id"])
                cur.execute(
                    "SELECT id FROM master.units WHERE code='KG' AND unit_type='WEIGHT' AND is_active=TRUE FOR SHARE"
                )
                kg_row = cur.fetchone()
                if not kg_row:
                    raise ValueError("Active KG weight unit is not configured.")
                kg_unit_id = int(kg_row["id"])
                cur.execute("SELECT id,code,is_company_owned FROM master.ownership_types WHERE is_active=TRUE FOR SHARE")
                ownership_map = {int(row["id"]): dict(row) for row in cur.fetchall()}

                # Validate raw yarn masters and optional existing batch references.
                for line in normalized_materials:
                    cur.execute(
                        """SELECT v.id,v.is_active AS variant_active,i.is_active AS item_active,
                                  i.is_stock_item,i.base_unit_id,base.code AS base_unit_code,
                                  base.unit_type,c.code AS category_code,
                                  v.yarn_count_id,v.fiber_type_id,v.brand_id,v.shade_id
                           FROM master.item_variants v
                           JOIN master.items i ON i.id=v.item_id
                           JOIN master.item_categories c ON c.id=i.item_category_id
                           JOIN master.units base ON base.id=i.base_unit_id
                           WHERE v.id=%s AND i.company_id=%s
                           FOR SHARE OF v,i""",
                        (line["item_variant_id"], company_id),
                    )
                    item = cur.fetchone()
                    if (not item or not item["variant_active"] or not item["item_active"]
                        or not item["is_stock_item"] or item["category_code"] != "YARN"
                        or item["base_unit_code"] != "KG" or item["unit_type"] != "WEIGHT"
                        or item["brand_id"] is not None or item["shade_id"] is not None
                        or item["yarn_count_id"] is None or item["fiber_type_id"] is None):
                        raise ValueError(
                            f"Yarn input {line['line_no']}: select an active stock YARN variant with KG base unit."
                        )
                    line["unit_id"] = kg_unit_id
                    line["location_id"] = location_id
                    line["process_stage_id"] = purchase_stage_id
                    line["ownership_type_id"] = own_type_id
                    if line["batch_id"] is not None:
                        cur.execute(
                            """SELECT 1 FROM inventory.batches b
                               WHERE b.id=%s AND b.company_id=%s AND b.item_variant_id=%s
                                 AND b.process_stage_id=%s AND b.ownership_type_id=%s
                                 AND b.owner_party_id IS NULL AND COALESCE(b.current_quantity,0)>0
                               FOR SHARE""",
                            (line["batch_id"],company_id,line["item_variant_id"],
                             purchase_stage_id,own_type_id),
                        )
                        if not cur.fetchone():
                            raise ValueError(
                                f"Yarn input {line['line_no']}: batch must be an available OWN raw-yarn batch for this item."
                            )

                for output in normalized_outputs:
                    source = next(x for x in normalized_materials
                                  if int(x["line_no"]) == int(output["source_line_no"]))
                    cur.execute(
                        """SELECT s.id AS shade_id,s.brand_id,src_v.item_id,
                                  src_v.yarn_count_id,src_v.fiber_type_id
                           FROM master.shades s
                           JOIN master.brands b ON b.id=s.brand_id
                           JOIN master.item_variants src_v ON src_v.id=%s
                           JOIN master.items src_i ON src_i.id=src_v.item_id
                           WHERE s.id=%s AND s.is_active=TRUE AND b.is_active=TRUE
                             AND src_i.company_id=%s AND src_i.item_code='YARN'
                           FOR SHARE OF s,b,src_v,src_i""",
                        (source["item_variant_id"],output["actual_shade_id"],company_id),
                    )
                    shade_identity=cur.fetchone()
                    if not shade_identity:
                        raise ValueError(f"DYED_THREAD output {output['line_no']}: select an active shade and raw-Yarn source.")
                    cur.execute(
                        """SELECT v.id
                           FROM master.item_variants v
                           JOIN master.items i ON i.id=v.item_id
                           WHERE i.company_id=%s AND i.item_code='YARN'
                             AND i.is_active=TRUE AND v.is_active=TRUE
                             AND v.item_id=%s
                             AND v.yarn_count_id IS NOT DISTINCT FROM %s
                             AND v.fiber_type_id IS NOT DISTINCT FROM %s
                             AND v.brand_id=%s AND v.shade_id=%s
                           ORDER BY v.id""",
                        (company_id,shade_identity["item_id"],shade_identity["yarn_count_id"],
                         shade_identity["fiber_type_id"],shade_identity["brand_id"],shade_identity["shade_id"]),
                    )
                    shade_variants=cur.fetchall()
                    if len(shade_variants)>1:
                        raise ValueError(
                            f"DYED_THREAD output {output['line_no']}: duplicate active Yarn variants exist for this exact count, fiber, brand and shade."
                        )
                    output["item_variant_id"]=(
                        int(shade_variants[0]["id"]) if shade_variants
                        else int(source["item_variant_id"])
                    )
                    output["shade_variant_resolved"]=bool(shade_variants)

                # Validate all dye/chemical lines before creating the header.
                for line in normalized:
                    cur.execute(
                        """SELECT v.id,v.is_active AS variant_active,i.is_active AS item_active,
                                  i.base_unit_id,base.unit_type AS base_unit_type,
                                  base.code AS base_unit_code,base.decimal_places AS base_decimal_places,
                                  c.code AS category_code,parent.code AS parent_code
                           FROM master.item_variants v
                           JOIN master.items i ON i.id=v.item_id
                           JOIN master.item_categories c ON c.id=i.item_category_id
                           JOIN master.item_categories parent ON parent.id=c.parent_category_id
                           JOIN master.units base ON base.id=i.base_unit_id
                           WHERE v.id=%s AND i.company_id=%s FOR SHARE OF v,i""",
                        (line["item_variant_id"], company_id),
                    )
                    item = cur.fetchone()
                    if not item or not item["variant_active"] or not item["item_active"] or item["parent_code"] != "DYE_CHEM":
                        raise ValueError(f"Line {line['line_no']}: select an active dye or chemical item.")
                    category_code = str(item["category_code"])
                    if category_code not in ALLOWED_DYE_CATEGORIES | ALLOWED_CHEMICAL_CATEGORIES:
                        raise ValueError(f"Line {line['line_no']}: item must belong to one of the five dyeing material groups.")
                    line["consumption_type"] = "DYE" if category_code in ALLOWED_DYE_CATEGORIES else "CHEMICAL"
                    cur.execute("SELECT id,code,unit_type,decimal_places FROM master.units WHERE id=%s AND is_active=TRUE FOR SHARE", (line["unit_id"],))
                    unit = cur.fetchone()
                    if not unit or unit["unit_type"] != item["base_unit_type"]:
                        raise ValueError(f"Line {line['line_no']}: selected unit must be active and match the item's measurement type.")
                    line["base_unit_id"] = int(item["base_unit_id"])
                    line["conversion"] = build_dyeing_unit_conversion_snapshot(
                        cur, company_id=company_id, effective_on=dyeing_date,
                        source_quantity=line["quantity"],
                        source_unit_code=unit["code"],
                        target_unit_code=item["base_unit_code"],
                        target_decimal_places=int(item["base_decimal_places"]),
                    )
                    owner = ownership_map.get(line["ownership_type_id"])
                    if not owner:
                        raise ValueError(f"Line {line['line_no']}: select an active ownership type.")
                    if owner["code"] == "OWN":
                        if line["owner_party_id"] is not None:
                            raise ValueError(f"Line {line['line_no']}: OWN material cannot have a party owner.")
                    elif owner["code"] == "PARTY":
                        if line["owner_party_id"] is None:
                            raise ValueError(f"Line {line['line_no']}: PARTY material requires an owner party.")
                        cur.execute("SELECT 1 FROM master.parties WHERE id=%s AND company_id=%s AND is_active=TRUE FOR SHARE", (line["owner_party_id"], company_id))
                        if not cur.fetchone():
                            raise ValueError(f"Line {line['line_no']}: selected party is not active in this company.")
                        validate_dyeing_party_use_authorization(owner["code"])
                    else:
                        raise ValueError(f"Line {line['line_no']}: unsupported ownership type.")

                    if line["batch_id"] is not None:
                        cur.execute(
                            """SELECT 1
                               FROM inventory.batches b
                               JOIN inventory.stock_balances sb
                                 ON sb.company_id=b.company_id AND sb.item_variant_id=b.item_variant_id
                                AND sb.batch_id=b.id AND sb.location_id=%s
                                AND sb.process_stage_id=%s
                                AND sb.ownership_type_id=b.ownership_type_id
                                AND sb.owner_party_id IS NOT DISTINCT FROM b.owner_party_id
                                AND sb.quantity>0
                               WHERE b.id=%s AND b.company_id=%s
                                 AND b.item_variant_id=%s AND b.process_stage_id=%s
                                 AND b.ownership_type_id=%s
                                 AND b.owner_party_id IS NOT DISTINCT FROM %s
                                 AND COALESCE(b.current_quantity,0)>0
                               FOR SHARE OF b,sb""",
                            (location_id,purchase_stage_id,line["batch_id"],company_id,
                             line["item_variant_id"],purchase_stage_id,line["ownership_type_id"],
                             line["owner_party_id"]),
                        )
                        if not cur.fetchone():
                            raise ValueError(
                                f"Line {line['line_no']}: batch must be available in RAW_STORE/PURCHASE "
                                "for the selected item and ownership/party."
                            )

                lock_key = f"dyeing:{company_id}:{dyeing_date.isoformat()}"
                cur.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (lock_key,))
                prefix = f"DY-{dyeing_date:%Y%m%d}-"
                cur.execute(
                    """SELECT COALESCE(MAX(substring(dyeing_no from %s)::integer),0)+1 AS next_no
                       FROM production.dyeing_orders
                       WHERE company_id=%s AND dyeing_no LIKE %s
                         AND substring(dyeing_no from %s) IS NOT NULL""",
                    (f"^{prefix}([0-9]+)$", company_id, prefix + "%", f"^{prefix}([0-9]+)$"),
                )
                next_no = int(cur.fetchone()["next_no"])
                dyeing_no = f"{prefix}{next_no:04d}"
                cur.execute(
                    """INSERT INTO production.dyeing_orders
                       (company_id,dyeing_no,dyeing_date,process_stage_id,status,created_by,remarks,
                        labour_cost,machine_cost,electricity_cost,water_cost,boiler_fuel_cost,
                        drying_cost,total_process_cost)
                       VALUES (%s,%s,%s,%s,'DRAFT',%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       RETURNING id,dyeing_no,dyeing_date,status,total_process_cost""",
                    (company_id,dyeing_no,dyeing_date,int(stage["id"]),user_id,remarks or None,
                     normalized_costs["labour_cost"],normalized_costs["machine_cost"],
                     normalized_costs["electricity_cost"],normalized_costs["water_cost"],
                     normalized_costs["boiler_fuel_cost"],normalized_costs["drying_cost"],
                     normalized_costs["total_process_cost"]),
                )
                order = dict(cur.fetchone())
                material_id_by_line_no = {}
                for line in normalized_materials:
                    cur.execute(
                        """INSERT INTO production.dyeing_material_lines
                           (dyeing_order_id,line_no,item_variant_id,batch_id,location_id,
                            ownership_type_id,owner_party_id,process_stage_id,quantity_kg,
                            unit_id,notes)
                           VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s)
                           RETURNING id,line_no,item_variant_id,batch_id,quantity_kg,unit_id""",
                        (order["id"],line["line_no"],line["item_variant_id"],line["batch_id"],
                         line["location_id"],line["ownership_type_id"],line["process_stage_id"],
                         line["quantity_kg"],line["unit_id"],line["notes"]),
                    )
                    saved_material = dict(cur.fetchone())
                    material_id_by_line_no[int(line["line_no"])] = int(saved_material["id"])
                    write_audit_log(
                        conn,user=user,request=request,action="CREATE",
                        table_name="production.dyeing_material_lines",record_id=saved_material["id"],
                        document_no=dyeing_no,new_values=saved_material,
                        reason="OWN raw-yarn input saved as DRAFT at RAW_STORE/PURCHASE; no stock movement or reservation.",
                        module="PRODUCTION",
                    )

                for output in normalized_outputs:
                    source = next(x for x in normalized_materials if int(x["line_no"]) == int(output["source_line_no"]))
                    cur.execute(
                        """INSERT INTO production.dyeing_output_lines
                           (dyeing_order_id,line_no,item_variant_id,batch_id,location_id,
                            ownership_type_id,owner_party_id,process_stage_id,output_type,
                            quantity_kg,unit_id,actual_shade_id,shade_match_status,
                            source_material_line_id,source_material_quantity_kg,notes)
                           VALUES (%s,%s,%s,NULL,%s,%s,NULL,%s,'DYED_THREAD',
                                   %s,%s,%s,'EXACT',%s,%s,%s)
                           RETURNING id,line_no,item_variant_id,batch_id,quantity_kg,
                                     source_material_line_id,source_material_quantity_kg,actual_shade_id""",
                        (order["id"],output["line_no"],output["item_variant_id"],
                         location_id,own_type_id,int(stage["id"]),output["quantity_kg"],kg_unit_id,
                         output["actual_shade_id"],material_id_by_line_no[int(output["source_line_no"])],
                         output["source_quantity_kg"],output["notes"]),
                    )
                    saved_output = dict(cur.fetchone())
                    write_audit_log(
                        conn,user=user,request=request,action="CREATE",
                        table_name="production.dyeing_output_lines",record_id=saved_output["id"],
                        document_no=dyeing_no,new_values=saved_output,
                        reason="Exact-shade DYED_THREAD output linked to its raw-yarn input; saved as DRAFT without stock movement.",
                        module="PRODUCTION",
                    )

                actual_input_kg = sum((x["quantity_kg"] for x in normalized_materials),Decimal("0"))
                actual_output_kg = sum((x["quantity_kg"] for x in normalized_outputs),Decimal("0"))
                cur.execute(
                    """UPDATE production.dyeing_orders
                       SET actual_input_quantity_kg=%s,actual_output_quantity_kg=%s,
                           updated_at=CURRENT_TIMESTAMP
                       WHERE id=%s AND company_id=%s AND status='DRAFT'""",
                    (actual_input_kg,actual_output_kg,order["id"],company_id),
                )
                if cur.rowcount != 1:
                    raise ValueError("Dyeing DRAFT totals could not be saved; transaction rolled back.")

                for line in normalized:
                    cur.execute(
                        """INSERT INTO production.dyeing_consumption_lines
                           (dyeing_order_id,line_no,item_variant_id,batch_id,location_id,
                            ownership_type_id,owner_party_id,quantity,unit_id,consumption_type,
                            source_material_line_id,notes)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                           RETURNING id,line_no,item_variant_id,batch_id,quantity,unit_id,
                                     consumption_type,source_material_line_id""",
                        (order["id"],line["line_no"],line["item_variant_id"],line["batch_id"],location_id,
                         line["ownership_type_id"],line["owner_party_id"],line["quantity"],
                         line["unit_id"],line["consumption_type"],
                         material_id_by_line_no[int(line["source_line_no"])],line["notes"]),
                    )
                    saved_line = dict(cur.fetchone())
                    conversion = line["conversion"]
                    cur.execute(
                        """INSERT INTO production.dyeing_unit_conversion_snapshots
                           (company_id,consumption_line_id,status,effective_on,
                            source_unit_id,source_unit_code,target_unit_id,target_unit_code,
                            source_quantity,converted_quantity,conversion_factor,
                            rounding_places,rounding_mode,configuration_version_id,snapshot)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (company_id,saved_line["id"],conversion["status"],conversion["effective_on"],
                         line["unit_id"],conversion["source_unit_code"],line["base_unit_id"],
                         conversion["target_unit_code"],conversion["source_quantity"],
                         conversion["converted_quantity"],conversion["conversion_factor"],
                         conversion["rounding_places"],conversion["rounding_mode"],
                         conversion["configuration_version_id"],Jsonb(conversion["snapshot"])),
                    )
                    write_audit_log(
                        conn,user=user,request=request,action="CREATE",
                        table_name="production.dyeing_consumption_lines",record_id=saved_line["id"],
                        document_no=dyeing_no,new_values={**saved_line,"unit_conversion":conversion["snapshot"]},
                        reason="Dyeing material consumption and its unit-conversion evidence saved as DRAFT; no stock movement.",module="PRODUCTION",
                    )
                write_audit_log(
                    conn,user=user,request=request,action="CREATE",
                    table_name="production.dyeing_orders",record_id=order["id"],
                    document_no=dyeing_no,new_values={**order,"dye_chemical_line_count":len(normalized),
                        "yarn_input_line_count":len(normalized_materials),
                        "dyed_thread_output_line_count":len(normalized_outputs),
                        "process_costs_pkr":{k:str(v) for k,v in normalized_costs.items()}},
                    reason="Dyeing order, exact raw-yarn/output lineage and actual process-cost entries saved as DRAFT; inventory posting is not performed.",module="PRODUCTION",
                )
    conversion_summary = {
        status: sum(1 for line in normalized if line["conversion"]["status"] == status)
        for status in ("NOT_REQUIRED", "APPROVED", "PENDING_CONFIGURATION", "BLOCKED_PRECISION")
    }
    return {"id": int(order["id"]), "dyeing_no": dyeing_no,
            "status": "DRAFT", "line_count": len(normalized),
            "yarn_input_line_count": len(normalized_materials),
            "dyed_thread_output_line_count": len(normalized_outputs),
            "process_cost_total": str(normalized_costs["total_process_cost"]),
            "conversion_summary": conversion_summary}



def get_dyeing_draft_detail(company_id: int, dyeing_order_id: int) -> dict[str, Any] | None:
    """Read-only, company-scoped view of a Dyeing order and pinned conversion evidence."""
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT id, dyeing_no, dyeing_date, status, remarks, created_at,
                              actual_input_quantity_kg,actual_output_quantity_kg,wastage_quantity_kg,
                              labour_cost,machine_cost,electricity_cost,water_cost,
                              boiler_fuel_cost,drying_cost,total_process_cost
                       FROM production.dyeing_orders
                       WHERE id=%s AND company_id=%s""",
                    (int(dyeing_order_id), int(company_id)),
                )
                order = cur.fetchone()
                if not order:
                    return None
                cur.execute(
                    """SELECT l.id AS line_id, l.line_no, l.quantity AS source_quantity,
                              su.code AS source_unit_code, su.name AS source_unit_name,
                              l.consumption_type, l.batch_id, batch.batch_no,
                              l.source_material_line_id,
                              source_material.line_no AS source_yarn_line_no,
                              source_variant.variant_code AS source_yarn_variant_code,
                              source_item.item_name AS source_yarn_item_name,
                              l.notes,i.item_code,i.item_name,
                              COALESCE(v.variant_name, v.variant_code) AS variant_name,
                              c.name AS category_name, own.code AS ownership_code,
                              own.name AS ownership_name, p.party_name,
                              bu.code AS base_unit_code, bu.name AS base_unit_name,
                              s.status AS conversion_status, s.converted_quantity,
                              s.conversion_factor, s.rounding_places, s.rounding_mode,
                              s.configuration_version_id, s.snapshot AS conversion_snapshot,
                              cv.version_no AS configuration_version_no,
                              cv.display_name AS configuration_display_name,
                              cv.config_key AS configuration_key
                       FROM production.dyeing_consumption_lines l
                       JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
                       JOIN master.item_variants v ON v.id=l.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.item_categories c ON c.id=i.item_category_id
                       JOIN master.units su ON su.id=l.unit_id
                       JOIN master.units bu ON bu.id=i.base_unit_id
                       JOIN master.ownership_types own ON own.id=l.ownership_type_id
                       LEFT JOIN master.parties p ON p.id=l.owner_party_id
                       LEFT JOIN inventory.batches batch ON batch.id=l.batch_id
                       LEFT JOIN production.dyeing_material_lines source_material
                         ON source_material.id=l.source_material_line_id
                        AND source_material.dyeing_order_id=l.dyeing_order_id
                       LEFT JOIN master.item_variants source_variant
                         ON source_variant.id=source_material.item_variant_id
                       LEFT JOIN master.items source_item ON source_item.id=source_variant.item_id
                       LEFT JOIN production.dyeing_unit_conversion_snapshots s
                         ON s.consumption_line_id=l.id AND s.company_id=o.company_id
                       LEFT JOIN configuration.config_versions cv
                         ON cv.id=s.configuration_version_id AND cv.company_id=o.company_id
                       WHERE o.id=%s AND o.company_id=%s
                       ORDER BY l.line_no""",
                    (int(dyeing_order_id), int(company_id)),
                )
                lines = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT l.id AS line_id,l.line_no,l.item_variant_id,l.batch_id,
                              l.quantity_kg,l.unit_id,u.code AS unit_code,
                              l.location_id,l.process_stage_id,l.notes,
                              i.item_code,i.item_name,v.variant_code,
                              COALESCE(v.variant_name,v.variant_code) AS variant_name,
                              COALESCE(sb.quantity,0) AS current_available_quantity_kg,
                              b.batch_no
                       FROM production.dyeing_material_lines l
                       JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
                       JOIN master.item_variants v ON v.id=l.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.units u ON u.id=l.unit_id
                       LEFT JOIN inventory.batches b ON b.id=l.batch_id
                       LEFT JOIN inventory.stock_balances sb
                         ON sb.company_id=o.company_id AND sb.item_variant_id=l.item_variant_id
                        AND sb.batch_id IS NOT DISTINCT FROM l.batch_id
                        AND sb.location_id=l.location_id AND sb.process_stage_id=l.process_stage_id
                        AND sb.ownership_type_id=l.ownership_type_id
                        AND sb.owner_party_id IS NOT DISTINCT FROM l.owner_party_id
                       WHERE o.id=%s AND o.company_id=%s
                       ORDER BY l.line_no""",
                    (int(dyeing_order_id),int(company_id)),
                )
                material_lines = [dict(row) for row in cur.fetchall()]
                cur.execute(
                    """SELECT l.id AS line_id,l.line_no,l.item_variant_id,l.batch_id,
                              l.quantity_kg,l.unit_id,u.code AS unit_code,l.output_type,
                              l.actual_shade_id,l.shade_match_status,l.source_material_line_id,
                              l.source_material_quantity_kg,l.notes,
                              i.item_code,i.item_name,v.variant_code,
                              COALESCE(v.variant_name,v.variant_code) AS variant_name,
                              s.shade_code,s.shade_name,b.code AS brand_code,b.name AS brand_name,
                              src.line_no AS source_line_no,src.batch_id AS source_batch_id,
                              output_batch.batch_no AS output_batch_no,
                              (v.brand_id=s.brand_id AND v.shade_id=s.id
                               AND v.yarn_count_id=source_v.yarn_count_id
                               AND v.fiber_type_id=source_v.fiber_type_id) AS shade_variant_exact
                       FROM production.dyeing_output_lines l
                       JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
                       JOIN master.item_variants v ON v.id=l.item_variant_id
                       JOIN master.items i ON i.id=v.item_id
                       JOIN master.units u ON u.id=l.unit_id
                       LEFT JOIN master.shades s ON s.id=l.actual_shade_id
                       LEFT JOIN master.brands b ON b.id=s.brand_id
                       LEFT JOIN production.dyeing_material_lines src ON src.id=l.source_material_line_id
                       LEFT JOIN master.item_variants source_v ON source_v.id=src.item_variant_id
                       LEFT JOIN inventory.batches output_batch ON output_batch.id=l.batch_id
                       WHERE o.id=%s AND o.company_id=%s
                       ORDER BY l.line_no""",
                    (int(dyeing_order_id),int(company_id)),
                )
                output_lines = [dict(row) for row in cur.fetchall()]
    for line in lines:
        snap = line.get("conversion_snapshot") or {}
        line["conversion_reason"] = snap.get("reason") or (
            "No approved directional conversion rule exists for this effective date."
            if line.get("conversion_status") == "PENDING_CONFIGURATION" else
            "Approved conversion exceeds the item's base-unit decimal precision."
            if line.get("conversion_status") == "BLOCKED_PRECISION" else ""
        )
    return {"order": dict(order), "lines": lines,
            "material_lines": material_lines, "output_lines": output_lines}



def _get_dyeing_approval_readiness_with_cursor(cur, company_id: int, dyeing_order_id: int) -> dict[str, Any] | None:
    """Read-only preflight for a future approval/post workflow; never reserves or changes stock."""
    company_id=int(company_id)
    dyeing_order_id=int(dyeing_order_id)
    blockers: list[str]=[]
    warnings: list[str]=[]
    checks={"raw_yarn_lines":0,"raw_yarn_ready":0,"output_lines":0,
            "shade_variants_ready":0,"chemical_lines":0,"chemical_lines_ready":0}

    cur.execute(
        """SELECT id,dyeing_no,status,total_process_cost
           FROM production.dyeing_orders
           WHERE id=%s AND company_id=%s""",
        (dyeing_order_id,company_id),
    )
    order=cur.fetchone()
    if not order:
        return None
    if order["status"]!="DRAFT":
        blockers.append(f"Order status is {order['status']}; preflight currently supports DRAFT only.")

    cur.execute(
        """SELECT il.id AS location_id
           FROM inventory.locations il JOIN core.locations cl ON cl.id=il.core_location_id
           WHERE cl.company_id=%s AND cl.code='RAW_STORE'
             AND cl.is_active=TRUE AND il.is_active=TRUE AND il.allow_stock=TRUE""",
        (company_id,),
    )
    loc=cur.fetchone()
    cur.execute(
        "SELECT id FROM master.process_stages WHERE company_id=%s AND code='PURCHASE' AND is_active=TRUE",
        (company_id,),
    )
    purchase_stage=cur.fetchone()
    cur.execute("SELECT id FROM master.ownership_types WHERE code='OWN' AND is_active=TRUE")
    own=cur.fetchone()
    location_id=int(loc["location_id"]) if loc else None
    purchase_stage_id=int(purchase_stage["id"]) if purchase_stage else None
    own_id=int(own["id"]) if own else None
    if location_id is None or purchase_stage_id is None or own_id is None:
        blockers.append("Active RAW_STORE, PURCHASE stage and OWN ownership masters are required.")

    cur.execute(
        """SELECT l.id,l.line_no,l.item_variant_id,l.batch_id,l.quantity_kg,
                  i.item_code,v.variant_code,
                  COALESCE(sb.quantity,0) AS available_quantity,
                  sb.average_unit_cost
           FROM production.dyeing_material_lines l
           JOIN production.dyeing_orders o ON o.id=l.dyeing_order_id
           JOIN master.item_variants v ON v.id=l.item_variant_id
           JOIN master.items i ON i.id=v.item_id
           LEFT JOIN inventory.stock_balances sb
             ON sb.company_id=o.company_id AND sb.item_variant_id=l.item_variant_id
            AND sb.batch_id IS NOT DISTINCT FROM l.batch_id
            AND sb.location_id=l.location_id
            AND sb.process_stage_id=l.process_stage_id
            AND sb.ownership_type_id=l.ownership_type_id
            AND sb.owner_party_id IS NOT DISTINCT FROM l.owner_party_id
           WHERE o.id=%s AND o.company_id=%s
           ORDER BY l.line_no""",
        (dyeing_order_id,company_id),
    )
    material_rows=[dict(r) for r in cur.fetchall()]
    checks["raw_yarn_lines"]=len(material_rows)
    if not material_rows:
        blockers.append("At least one raw-yarn input line is required.")
    for row in material_rows:
        if row["batch_id"] is None:
            blockers.append(f"Yarn input line {row['line_no']}: assign a received OWN batch before approval.")
            continue
        if row["available_quantity"] < row["quantity_kg"]:
            blockers.append(
                f"Yarn input line {row['line_no']}: RAW_STORE/PURCHASE available "
                f"{row['available_quantity']} KG; required {row['quantity_kg']} KG."
            )
            continue
        if row["average_unit_cost"] is None:
            blockers.append(f"Yarn input line {row['line_no']}: batch has no verified unit-cost valuation.")
            continue
        checks["raw_yarn_ready"]+=1

    cur.execute(
        """SELECT l.id,l.line_no,l.quantity_kg,
                  COALESCE(SUM(o.source_material_quantity_kg),0) AS allocated_quantity
           FROM production.dyeing_material_lines l
           LEFT JOIN production.dyeing_output_lines o
             ON o.source_material_line_id=l.id
           JOIN production.dyeing_orders d ON d.id=l.dyeing_order_id
           WHERE d.id=%s AND d.company_id=%s
           GROUP BY l.id,l.line_no,l.quantity_kg
           ORDER BY l.line_no""",
        (dyeing_order_id,company_id),
    )
    for row in cur.fetchall():
        if row["allocated_quantity"]!=row["quantity_kg"]:
            blockers.append(
                f"Yarn input line {row['line_no']}: {row['allocated_quantity']} KG is allocated "
                f"to shade outputs out of {row['quantity_kg']} KG input; reconcile unused material or measured wastage."
            )

    cur.execute(
        """SELECT o.id,o.line_no,o.actual_shade_id,o.item_variant_id,
                  o.batch_id AS output_batch_id,s.shade_code,s.shade_name,
                  src_v.yarn_count_id,src_v.fiber_type_id,sh.brand_id,
                  output_v.brand_id AS output_brand_id,
                  output_v.shade_id AS output_shade_id,
                  output_v.yarn_count_id AS output_yarn_count_id,
                  output_v.fiber_type_id AS output_fiber_type_id,
                  output_i.item_code AS output_item_code,
                  EXISTS(
                    SELECT 1
                    FROM master.item_variants dyed_v
                    JOIN master.items dyed_i ON dyed_i.id=dyed_v.item_id
                    WHERE dyed_i.company_id=d.company_id
                      AND dyed_i.item_code='YARN'
                      AND dyed_i.is_active=TRUE
                      AND dyed_v.is_active=TRUE
                      AND dyed_v.yarn_count_id IS NOT DISTINCT FROM src_v.yarn_count_id
                      AND dyed_v.fiber_type_id IS NOT DISTINCT FROM src_v.fiber_type_id
                      AND dyed_v.brand_id=sh.brand_id
                      AND dyed_v.shade_id=sh.id
                  ) AS shade_variant_exists,
                  (output_i.item_code='YARN'
                   AND output_v.brand_id=sh.brand_id
                   AND output_v.shade_id=sh.id
                   AND output_v.yarn_count_id IS NOT DISTINCT FROM src_v.yarn_count_id
                   AND output_v.fiber_type_id IS NOT DISTINCT FROM src_v.fiber_type_id
                  ) AS output_variant_exact
           FROM production.dyeing_output_lines o
           JOIN production.dyeing_orders d ON d.id=o.dyeing_order_id
           JOIN production.dyeing_material_lines src ON src.id=o.source_material_line_id
           JOIN master.item_variants src_v ON src_v.id=src.item_variant_id
           JOIN master.shades sh ON sh.id=o.actual_shade_id
           JOIN master.item_variants output_v ON output_v.id=o.item_variant_id
           JOIN master.items output_i ON output_i.id=output_v.item_id
           JOIN master.shades s ON s.id=o.actual_shade_id
           WHERE d.id=%s AND d.company_id=%s
           ORDER BY o.line_no""",
        (dyeing_order_id,company_id),
    )
    output_rows=cur.fetchall()
    checks["output_lines"]=len(output_rows)
    if not output_rows:
        blockers.append("At least one DYED_THREAD output line is required.")