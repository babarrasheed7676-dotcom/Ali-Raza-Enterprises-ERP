"""Audited CRUD for shared configuration master data.

No hard deletes. Existing identities and accounting/inventory references remain stable.
"""
from __future__ import annotations

from .db import get_connection
from .audit_service import write_audit_log

_ALLOWED_TYPES = {"BRAND", "UNIT", "SHADE", "VARIANT", "YARN_COUNT", "FIBER_TYPE", "SHADE_CATEGORY", "ITEM_CATEGORY", "ITEM"}


def _text(value, field, maximum, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{field} is required.")
    if len(value) > maximum:
        raise ValueError(f"{field} cannot exceed {maximum} characters.")
    return value or None


def _bool(value, field="Active"):
    if isinstance(value, bool):
        return value
    if value in (1, "1", "true", "True", "on", "yes"):
        return True
    if value in (0, "0", "false", "False", "off", "no"):
        return False
    raise ValueError(f"{field} must be true or false.")


def _positive_id(value, field):
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a valid selection.")
    if result <= 0:
        raise ValueError(f"{field} must be a valid selection.")
    return result


def _optional_positive_id(value, field):
    if value in (None, ""):
        return None
    return _positive_id(value, field)


def validate_variant_identity(*, item_code: str, brand_id: int | None,
                              shade_id: int | None, shade_brand_id: int | None,
                              yarn_count_id: int | None, fiber_type_id: int | None) -> int | None:
    code = str(item_code or "").strip().upper()
    if shade_id is not None:
        if shade_brand_id is None:
            raise ValueError("Selected shade must belong to an active brand.")
        if brand_id is not None and int(brand_id) != int(shade_brand_id):
            raise ValueError("Selected shade does not belong to the selected brand.")
        brand_id = int(shade_brand_id)
    if code in ("NALKI", "LABEL") and (not brand_id or not shade_id):
        raise ValueError("Nalki and Label variants require an active brand and a shade belonging to that brand.")
    if code in ("YARN", "BIG_CONE", "BABY_CONE") and (not yarn_count_id or not fiber_type_id):
        raise ValueError("Yarn, Big Cone and Baby Cone variants require both yarn count and fiber type.")
    return brand_id


def _shade_usage_from_category_code(code: str) -> tuple[str, bool]:
    normalized = str(code or "").strip().upper()
    if normalized not in {"LADIES", "GENTS", "COMMON"}:
        raise ValueError("Shade usage must be Ladies, Gents or Common.")
    return normalized, normalized == "COMMON"


def save_configuration_master_record(*, record_type: str, payload: dict,
                                      user: dict, request, record_id: int | None = None) -> dict:
    kind = str(record_type or "").strip().upper()
    if kind not in _ALLOWED_TYPES:
        raise ValueError("Unsupported master-data type.")
    if not isinstance(payload, dict):
        raise ValueError("Master-data payload must be a JSON object.")

    actor = int(user["id"])
    company_id = int(user["company_id"])
    creating = record_id is None

    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                old = None
                if not creating:
                    rid = _positive_id(record_id, "Record ID")
                    table = {"BRAND":"brands", "UNIT":"units", "SHADE":"shades", "VARIANT":"item_variants", "YARN_COUNT":"yarn_counts", "FIBER_TYPE":"fiber_types", "SHADE_CATEGORY":"shade_categories", "ITEM_CATEGORY":"item_categories", "ITEM":"items"}[kind]
                    if kind in {"ITEM_CATEGORY", "ITEM"}:
                        cur.execute(f"SELECT * FROM master.{table} WHERE id=%s AND company_id=%s FOR UPDATE", (rid, company_id))
                    else:
                        cur.execute(f"SELECT * FROM master.{table} WHERE id=%s FOR UPDATE", (rid,))
                    old = cur.fetchone()
                    if not old:
                        raise ValueError("Master-data record was not found.")
                    old = dict(old)

                if kind == "BRAND":
                    if creating:
                        code = _text(payload.get("code"), "Brand code", 50).upper()
                        name = _text(payload.get("name"), "Brand name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.brands(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Brand name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("""SELECT
                                EXISTS(SELECT 1 FROM master.shades WHERE brand_id=%s AND is_active)
                                OR EXISTS(SELECT 1 FROM master.item_variants WHERE brand_id=%s AND is_active)
                                OR EXISTS(SELECT 1 FROM inventory.stock_balances b
                                          JOIN master.item_variants v ON v.id=b.item_variant_id
                                          WHERE v.brand_id=%s AND b.quantity<>0) AS in_use""", (rid,rid,rid))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Brand cannot be deactivated while active shades, active variants or stock depend on it. Deactivate dependent records first.")
                        cur.execute("""UPDATE master.brands SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.brands"

                elif kind == "UNIT":
                    if creating:
                        code = _text(payload.get("code"), "Unit code", 30).upper()
                        name = _text(payload.get("name"), "Unit name", 100)
                        unit_type = _text(payload.get("unit_type"), "Unit type", 50).upper()
                        decimals = int(payload.get("decimal_places", 3))
                        if decimals < 0 or decimals > 6:
                            raise ValueError("Decimal places must be between 0 and 6.")
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.units(code,name,unit_type,decimal_places,is_active)
                                       VALUES (%s,%s,%s,%s,%s) RETURNING id,code,name,unit_type,decimal_places,is_active""",
                                    (code,name,unit_type,decimals,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Unit name", 100)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("""SELECT EXISTS(SELECT 1 FROM master.items WHERE base_unit_id=%s)
                                OR EXISTS(SELECT 1 FROM master.item_variants WHERE default_unit_id=%s)
                                OR EXISTS(SELECT 1 FROM master.machines WHERE capacity_unit_id=%s) AS in_use""",
                                (rid,rid,rid))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Unit is referenced by an item, variant or machine. Keep it active; do not deactivate a unit in use.")
                        cur.execute("""UPDATE master.units SET name=%s,is_active=%s WHERE id=%s
                                       RETURNING id,code,name,unit_type,decimal_places,is_active""",
                                    (name,active,rid))
                    table = "master.units"

                elif kind == "SHADE":
                    if creating:
                        brand_id = _positive_id(payload.get("brand_id"), "Brand")
                        code = _text(payload.get("shade_code"), "Shade code", 30).upper()
                        name = _text(payload.get("shade_name"), "Shade name", 150, False)
                        category_id = _positive_id(payload.get("shade_category_id"), "Shade usage")
                        active = _bool(payload.get("is_active", True))
                        cur.execute("SELECT 1 FROM master.brands WHERE id=%s AND is_active", (brand_id,))
                        if not cur.fetchone():
                            raise ValueError("Select an active brand.")
                        cur.execute("SELECT code FROM master.shade_categories WHERE id=%s AND is_active", (category_id,))
                        category = cur.fetchone()
                        if not category:
                            raise ValueError("Select an active shade usage category.")
                        _, common = _shade_usage_from_category_code(category["code"])
                        cur.execute("""INSERT INTO master.shades(brand_id,shade_category_id,shade_code,shade_name,is_common,is_active)
                                       VALUES (%s,%s,%s,%s,%s,%s)
                                       RETURNING id,brand_id,shade_category_id,shade_code,shade_name,is_common,is_active""",
                                    (brand_id,category_id,code,name,common,active))
                    else:
                        name = _text(payload.get("shade_name", old.get("shade_name")), "Shade name", 150, False)
                        category_id = _positive_id(payload.get("shade_category_id", old.get("shade_category_id")), "Shade usage")
                        active = _bool(payload.get("is_active", old["is_active"]))
                        cur.execute("SELECT code FROM master.shade_categories WHERE id=%s AND is_active", (category_id,))
                        category = cur.fetchone()
                        if not category:
                            raise ValueError("Select an active shade usage category.")
                        _, common = _shade_usage_from_category_code(category["code"])
                        if not active and old["is_active"]:
                            cur.execute("""SELECT EXISTS(SELECT 1 FROM master.item_variants
                                WHERE shade_id=%s AND is_active)
                                OR EXISTS(SELECT 1 FROM master.item_variants v
                                          JOIN inventory.stock_balances b ON b.item_variant_id=v.id
                                          WHERE v.shade_id=%s AND b.quantity<>0) AS in_use""", (rid,rid))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Shade cannot be deactivated while active variants or stock depend on it. Deactivate dependent variants first.")
                        cur.execute("""UPDATE master.shades SET shade_name=%s,shade_category_id=%s,
                                       is_common=%s,is_active=%s,updated_at=CURRENT_TIMESTAMP
                                       WHERE id=%s RETURNING id,brand_id,shade_category_id,shade_code,shade_name,is_common,is_active""",
                                    (name,category_id,common,active,rid))
                    table = "master.shades"

                elif kind == "YARN_COUNT":
                    if creating:
                        code = _text(payload.get("code"), "Yarn count code", 30).upper()
                        name = _text(payload.get("name"), "Yarn count name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.yarn_counts(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Yarn count name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.item_variants WHERE yarn_count_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Yarn count is referenced by item variants and cannot be deactivated.")
                        cur.execute("""UPDATE master.yarn_counts SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.yarn_counts"

                elif kind == "FIBER_TYPE":
                    if creating:
                        code = _text(payload.get("code"), "Fiber type code", 30).upper()
                        name = _text(payload.get("name"), "Fiber type name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.fiber_types(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Fiber type name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.item_variants WHERE fiber_type_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Fiber type is referenced by item variants and cannot be deactivated.")
                        cur.execute("""UPDATE master.fiber_types SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.fiber_types"

                elif kind == "SHADE_CATEGORY":
                    if creating:
                        code = _text(payload.get("code"), "Shade category code", 30).upper()
                        name = _text(payload.get("name"), "Shade category name", 100)
                        description = _text(payload.get("description"), "Description", 300, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.shade_categories(code,name,description,is_active)
                                       VALUES (%s,%s,%s,%s) RETURNING id,code,name,is_active""",
                                    (code,name,description,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Shade category name", 100)
                        description = _text(payload.get("description", old.get("description")), "Description", 300, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM master.shades WHERE shade_category_id=%s) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Shade category is referenced by shades and cannot be deactivated.")
                        cur.execute("""UPDATE master.shade_categories SET name=%s,description=%s,is_active=%s
                                       WHERE id=%s RETURNING id,code,name,is_active""",
                                    (name,description,active,rid))
                    table = "master.shade_categories"

                elif kind == "ITEM_CATEGORY":
                    if creating:
                        code = _text(payload.get("code"), "Item category code", 50).upper()
                        name = _text(payload.get("name"), "Item category name", 150)
                        description = _text(payload.get("description"), "Description", 500, False)
                        parent_id = _optional_positive_id(payload.get("parent_category_id"), "Parent category")
                        active = _bool(payload.get("is_active", True))
                        if parent_id:
                            cur.execute("""SELECT 1 FROM master.item_categories
                                           WHERE id=%s AND company_id=%s AND is_active FOR SHARE""",
                                        (parent_id, company_id))
                            if not cur.fetchone():
                                raise ValueError("Select an active parent category in this company.")
                        cur.execute("""INSERT INTO master.item_categories
                            (company_id,code,name,description,parent_category_id,is_active)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            RETURNING id,company_id,code,name,description,parent_category_id,is_active""",
                            (company_id,code,name,description,parent_id,active))
                    else:
                        name = _text(payload.get("name", old["name"]), "Item category name", 150)
                        description = _text(payload.get("description", old.get("description")), "Description", 500, False)
                        parent_id = _optional_positive_id(payload.get("parent_category_id", old.get("parent_category_id")), "Parent category")
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if parent_id:
                            if parent_id == rid:
                                raise ValueError("A category cannot be its own parent.")
                            cur.execute("""SELECT 1 FROM master.item_categories
                                           WHERE id=%s AND company_id=%s AND is_active FOR SHARE""",
                                        (parent_id, company_id))
                            if not cur.fetchone():
                                raise ValueError("Select an active parent category in this company.")
                            cur.execute("""WITH RECURSIVE descendants(id) AS (
                                SELECT id FROM master.item_categories
                                WHERE parent_category_id=%s AND company_id=%s
                                UNION
                                SELECT c.id FROM master.item_categories c
                                JOIN descendants d ON c.parent_category_id=d.id
                                WHERE c.company_id=%s
                            ) SELECT EXISTS(SELECT 1 FROM descendants WHERE id=%s) AS cycle""",
                                (rid,company_id,company_id,parent_id))
                            if cur.fetchone()["cycle"]:
                                raise ValueError("A category cannot be moved beneath one of its descendants.")
                        if not active and old["is_active"]:
                            cur.execute("""SELECT
                                EXISTS(SELECT 1 FROM master.items WHERE item_category_id=%s AND company_id=%s AND is_active)
                                OR EXISTS(SELECT 1 FROM master.item_categories WHERE parent_category_id=%s AND company_id=%s AND is_active)
                                AS in_use""", (rid,company_id,rid,company_id))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Category cannot be deactivated while active items or active child categories depend on it.")
                        cur.execute("""UPDATE master.item_categories
                            SET name=%s,description=%s,parent_category_id=%s,is_active=%s,updated_at=CURRENT_TIMESTAMP
                            WHERE id=%s AND company_id=%s
                            RETURNING id,company_id,code,name,description,parent_category_id,is_active""",
                            (name,description,parent_id,active,rid,company_id))
                    table = "master.item_categories"

                elif kind == "ITEM":
                    if creating:
                        code = _text(payload.get("item_code"), "Item code", 100).upper()
                        name = _text(payload.get("item_name"), "Item name", 250)
                        description = _text(payload.get("description"), "Description", 500, False)
                        category_id = _positive_id(payload.get("item_category_id"), "Item category")
                        unit_id = _positive_id(payload.get("base_unit_id"), "Base unit")
                        cur.execute("""SELECT 1 FROM master.item_categories
                            WHERE id=%s AND company_id=%s AND is_active FOR SHARE""",
                            (category_id,company_id))
                        if not cur.fetchone():
                            raise ValueError("Select an active item category in this company.")
                        cur.execute("SELECT 1 FROM master.units WHERE id=%s AND is_active FOR SHARE", (unit_id,))
                        if not cur.fetchone():
                            raise ValueError("Select an active base unit.")
                        track_batch = _bool(payload.get("track_batch", False), "Track batch")
                        track_shade = _bool(payload.get("track_shade", False), "Track shade")
                        track_ownership = _bool(payload.get("track_ownership", True), "Track ownership")
                        is_stock_item = _bool(payload.get("is_stock_item", True), "Stock item")
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""INSERT INTO master.items
                            (company_id,item_category_id,item_code,item_name,description,base_unit_id,
                             track_batch,track_shade,track_ownership,is_stock_item,is_active)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id,company_id,item_category_id,item_code,item_name,description,
                                      base_unit_id,track_batch,track_shade,track_ownership,is_stock_item,is_active""",
                            (company_id,category_id,code,name,description,unit_id,track_batch,
                             track_shade,track_ownership,is_stock_item,active))
                    else:
                        name = _text(payload.get("item_name", old["item_name"]), "Item name", 250)
                        description = _text(payload.get("description", old.get("description")), "Description", 500, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("""SELECT
                                EXISTS(SELECT 1 FROM master.item_variants WHERE item_id=%s AND is_active)
                                OR EXISTS(SELECT 1 FROM inventory.stock_balances b
                                          JOIN master.item_variants v ON v.id=b.item_variant_id
                                          WHERE v.item_id=%s AND b.quantity<>0) AS in_use""", (rid,rid))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Item cannot be deactivated while active variants or non-zero stock depend on it.")
                        cur.execute("""UPDATE master.items
                            SET item_name=%s,description=%s,is_active=%s,updated_at=CURRENT_TIMESTAMP
                            WHERE id=%s AND company_id=%s
                            RETURNING id,company_id,item_category_id,item_code,item_name,description,
                                      base_unit_id,track_batch,track_shade,track_ownership,is_stock_item,is_active""",
                            (name,description,active,rid,company_id))
                    table = "master.items"

                else:  # VARIANT: create only with a complete, validated item identity.
                    if creating:
                        item_id = _positive_id(payload.get("item_id"), "Item")
                        code = _text(payload.get("variant_code"), "Variant code", 100).upper()
                        name = _text(payload.get("variant_name"), "Variant name", 250, False)
                        active = _bool(payload.get("is_active", True))
                        cur.execute("""SELECT id,item_code,item_name,base_unit_id,track_shade,is_stock_item,is_active
                                       FROM master.items WHERE id=%s FOR SHARE""", (item_id,))
                        item = cur.fetchone()
                        if not item or not item["is_active"]:
                            raise ValueError("Select an active item.")
                        item = dict(item)
                        unit_id = _optional_positive_id(payload.get("default_unit_id"), "Default unit") or int(item["base_unit_id"])
                        cur.execute("SELECT id,is_active FROM master.units WHERE id=%s FOR SHARE", (unit_id,))
                        unit = cur.fetchone()
                        if not unit or not unit["is_active"]:
                            raise ValueError("Select an active default unit.")
                        if unit_id != int(item["base_unit_id"]):
                            raise ValueError("Variant default unit must match the item's base unit. Unit conversions are configured separately.")

                        brand_id = _optional_positive_id(payload.get("brand_id"), "Brand")
                        shade_id = _optional_positive_id(payload.get("shade_id"), "Shade")
                        yarn_count_id = _optional_positive_id(payload.get("yarn_count_id"), "Yarn count")
                        fiber_type_id = _optional_positive_id(payload.get("fiber_type_id"), "Fiber type")

                        if brand_id:
                            cur.execute("SELECT id FROM master.brands WHERE id=%s AND is_active FOR SHARE", (brand_id,))
                            if not cur.fetchone():
                                raise ValueError("Select an active brand.")
                        shade_brand_id = None
                        if shade_id:
                            cur.execute("SELECT id,brand_id FROM master.shades WHERE id=%s AND is_active FOR SHARE", (shade_id,))
                            shade = cur.fetchone()
                            if not shade:
                                raise ValueError("Select an active shade.")
                            shade_brand_id = int(shade["brand_id"])
                        brand_id = validate_variant_identity(
                            item_code=item["item_code"], brand_id=brand_id,
                            shade_id=shade_id, shade_brand_id=shade_brand_id,
                            yarn_count_id=yarn_count_id, fiber_type_id=fiber_type_id,
                        )
                        if yarn_count_id:
                            cur.execute("SELECT 1 FROM master.yarn_counts WHERE id=%s AND is_active FOR SHARE", (yarn_count_id,))
                            if not cur.fetchone():
                                raise ValueError("Select an active yarn count.")
                        if fiber_type_id:
                            cur.execute("SELECT 1 FROM master.fiber_types WHERE id=%s AND is_active FOR SHARE", (fiber_type_id,))
                            if not cur.fetchone():
                                raise ValueError("Select an active fiber type.")

                        cur.execute("""INSERT INTO master.item_variants
                            (item_id,variant_code,variant_name,yarn_count_id,fiber_type_id,
                             brand_id,shade_id,default_unit_id,is_active)
                            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            RETURNING id,item_id,variant_code,variant_name,yarn_count_id,
                                      fiber_type_id,brand_id,shade_id,default_unit_id,is_active""",
                            (item_id,code,name,yarn_count_id,fiber_type_id,brand_id,shade_id,unit_id,active))
                    else:
                        name = _text(payload.get("variant_name", old.get("variant_name")), "Variant name", 250, False)
                        active = _bool(payload.get("is_active", old["is_active"]))
                        if not active and old["is_active"]:
                            cur.execute("SELECT EXISTS(SELECT 1 FROM inventory.stock_balances WHERE item_variant_id=%s AND quantity<>0) AS in_use", (rid,))
                            if cur.fetchone()["in_use"]:
                                raise ValueError("Variant cannot be deactivated while any stock balance is non-zero.")
                        cur.execute("""UPDATE master.item_variants SET variant_name=%s,is_active=%s,
                                       updated_at=CURRENT_TIMESTAMP WHERE id=%s
                                       RETURNING id,variant_code,variant_name,is_active""", (name,active,rid))
                    table = "master.item_variants"

                row = dict(cur.fetchone())
                new_values = dict(row)
                write_audit_log(
                    conn,user=user,request=request,
                    action="CREATE" if creating else "UPDATE",
                    table_name=table,record_id=row["id"],
                    document_no=row.get("code") or row.get("item_code") or row.get("shade_code") or row.get("variant_code"),
                    old_values=old if old else None,new_values=new_values,
                    reason="Configuration master data create" if creating else "Configuration master data update",
                    module="CONFIGURATION",
                )
    return {"id": int(row["id"]), "record_type": kind, "created": creating, "record": row}
