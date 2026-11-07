"""Resolve and pin approved configuration rules to operational packing drafts."""
from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from .configuration_rules import PackagingRule


PACKAGING_CONFIG_TYPE = "PACKAGING_RULE"
PACKAGING_CONFIG_KEY = "NALKI-FINISHED-WALL-BOX"

SYSTEM_DEFAULT_NALKI_PACKAGING = {
    "effective_from": "2026-11-05",
    "product_type": "Nalki",
    "product_code": "NALKI",
    "packaging_code": "FINISHED-WALL-BOX",
    "base_unit_code": "PCS",
    "units_per_pack": 100,
    "inner_packaging_code": "PACK_BOX-STD",
    "inner_packs_per_pack": 10,
    "net_weight_grams": None,
    "active": True,
}


def validate_nalki_packaging_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the currently approved Nalki pack relationship; fail closed on drift."""
    rule = PackagingRule.model_validate(payload)
    normalized = rule.model_dump(mode="json")
    if not rule.active:
        raise ValueError("The approved Nalki finished-box packaging rule is inactive.")
    if rule.product_type.strip().casefold() != "nalki":
        raise ValueError("Nalki packaging rule product_type must be Nalki.")
    if rule.product_code and rule.product_code.strip().upper() != "NALKI":
        raise ValueError("Nalki packaging rule product_code must be NALKI.")
    if rule.packaging_code.strip().upper() != "FINISHED-WALL-BOX":
        raise ValueError("Nalki finished pack code must remain FINISHED-WALL-BOX.")
    if rule.base_unit_code and rule.base_unit_code.strip().upper() != "PCS":
        raise ValueError("Nalki finished-box base unit must remain PCS.")
    if rule.units_per_pack != 100:
        raise ValueError("Nalki finished wall box must contain exactly 100 pieces.")
    if rule.inner_packaging_code != "PACK_BOX-STD":
        raise ValueError("Nalki finished wall box must contain regular PACK_BOX-STD boxes.")
    if rule.inner_packs_per_pack != 10:
        raise ValueError("Nalki finished wall box must contain exactly 10 regular boxes.")
    return normalized


def resolve_nalki_packaging_snapshot(cur, *, company_id: int, effective_on: date) -> dict[str, Any]:
    """Resolve one approved version for the packing date, otherwise pin system default."""
    cur.execute(
        """SELECT id,payload,effective_from,effective_to
           FROM configuration.config_versions
           WHERE company_id=%s AND config_type=%s AND config_key=%s
             AND status='APPROVED'
             AND effective_from<=%s
             AND (effective_to IS NULL OR effective_to>=%s)
           ORDER BY version_no DESC
           FOR SHARE""",
        (int(company_id), PACKAGING_CONFIG_TYPE, PACKAGING_CONFIG_KEY,
         effective_on, effective_on),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise RuntimeError("More than one approved Nalki packaging rule is effective for this packing date.")
    if not rows:
        payload = dict(SYSTEM_DEFAULT_NALKI_PACKAGING)
        payload["effective_from"] = effective_on.isoformat()
        return {
            "config_type": PACKAGING_CONFIG_TYPE,
            "config_key": PACKAGING_CONFIG_KEY,
            "configuration_version_id": None,
            "source": "SYSTEM_DEFAULT",
            "effective_on": effective_on,
            "payload": validate_nalki_packaging_payload(payload),
        }

    row = dict(rows[0])
    payload = validate_nalki_packaging_payload(dict(row["payload"]))
    return {
        "config_type": PACKAGING_CONFIG_TYPE,
        "config_key": PACKAGING_CONFIG_KEY,
        "configuration_version_id": int(row["id"]),
        "source": "APPROVED_VERSION",
        "effective_on": effective_on,
        "payload": payload,
    }


def insert_packing_configuration_snapshot(
    cur, *, company_id: int, packing_order_id: int, user_id: int,
    snapshot: dict[str, Any],
) -> None:
    """Persist the immutable rule version/payload beside its DRAFT packing order."""
    cur.execute(
        """INSERT INTO production.packing_configuration_snapshots
           (company_id,packing_order_id,config_type,config_key,
            configuration_version_id,source,effective_on,payload_snapshot,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            int(company_id), int(packing_order_id), snapshot["config_type"],
            snapshot["config_key"], snapshot["configuration_version_id"],
            snapshot["source"], snapshot["effective_on"],
            Jsonb(snapshot["payload"]), int(user_id),
        ),
    )


def resolve_purchase_line_configuration_snapshots(
    cur, *, company_id: int, effective_on: date,
    item_master: dict[str, Any], unit_master: dict[str, Any],
) -> list[dict[str, Any]]:
    """Resolve approved Product/Unit rules or pin exact active-master baselines.

    This phase validates identity only. It deliberately does not apply unit
    conversions or change the receipt's existing unit/quantity semantics.
    """
    from decimal import Decimal
    from .configuration_rules import ProductDefinition, UnitDefinition

    def resolve(config_type: str, config_key: str, master_payload: dict[str, Any], model):
        cur.execute(
            """SELECT id,payload,effective_from,effective_to
               FROM configuration.config_versions
               WHERE company_id=%s AND config_type=%s AND config_key=%s
                 AND status='APPROVED' AND effective_from<=%s
                 AND (effective_to IS NULL OR effective_to>=%s)
               ORDER BY version_no DESC FOR SHARE""",
            (int(company_id), config_type, config_key, effective_on, effective_on),
        )
        rows = cur.fetchall()
        if len(rows) > 1:
            raise RuntimeError(
                f"Multiple approved {config_type} versions are effective for {config_key}."
            )
        if not rows:
            return {
                "config_type": config_type,
                "config_key": config_key,
                "configuration_version_id": None,
                "source": "SYSTEM_DEFAULT_MASTER",
                "effective_on": effective_on,
                "payload": master_payload,
            }

        row = dict(rows[0])
        payload = dict(row["payload"])
        validated = model.model_validate(payload)
        if validated.code != config_key:
            raise ValueError(f"Approved {config_type} code does not match {config_key}.")
        if isinstance(validated, ProductDefinition) and not validated.active:
            raise ValueError(f"Approved product definition {config_key} is inactive.")
        if isinstance(validated, UnitDefinition):
            if validated.base_unit_code not in (None, config_key) or validated.factor_to_base != Decimal("1"):
                raise ValueError(
                    f"Approved unit definition {config_key} requires a conversion. "
                    "Purchasing conversion is not enabled yet; use the item's exact base unit."
                )
        return {
            "config_type": config_type,
            "config_key": config_key,
            "configuration_version_id": int(row["id"]),
            "source": "APPROVED_VERSION",
            "effective_on": effective_on,
            "payload": payload,
        }

    product_payload = {
        "master_id": int(item_master["id"]),
        "code": str(item_master["item_code"]),
        "name": str(item_master["item_name"]),
    }
    unit_payload = {
        "master_id": int(unit_master["id"]),
        "code": str(unit_master["code"]),
        "name": str(unit_master["name"]),
        "decimal_places": int(unit_master["decimal_places"]),
    }
    return [
        resolve("PRODUCT_DEFINITION", product_payload["code"], product_payload, ProductDefinition),
        resolve("UNIT_DEFINITION", unit_payload["code"], unit_payload, UnitDefinition),
    ]


def insert_purchase_configuration_snapshot(
    cur, *, company_id: int, receipt_id: int, receipt_line_id: int,
    user_id: int, snapshot: dict[str, Any],
) -> None:
    """Attach an immutable approved-version or master-baseline snapshot to a DRAFT GRN line."""
    from psycopg.types.json import Jsonb

    cur.execute(
        """INSERT INTO purchasing.purchase_configuration_snapshots
           (company_id,purchase_receipt_id,purchase_receipt_line_id,
            config_type,config_key,configuration_version_id,source,
            effective_on,payload_snapshot,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            int(company_id), int(receipt_id), int(receipt_line_id),
            snapshot["config_type"], snapshot["config_key"],
            snapshot["configuration_version_id"], snapshot["source"],
            snapshot["effective_on"], Jsonb(snapshot["payload"]), int(user_id),
        ),
    )


BABY_CONE_PROFILE_CONFIG_TYPE = "MEASUREMENT_PROFILE"


def resolve_baby_cone_measurement_profile_snapshot(
    cur, *, company_id: int, effective_on: date,
    config_key: str, variant_code: str,
) -> dict[str, Any]:
    """Resolve one approved Baby Cone weight/length profile; never invent a fallback."""
    key = str(config_key or "").strip().upper()
    variant = str(variant_code or "").strip().upper()
    if not key or not variant:
        raise ValueError("A measurement profile key and variant code are required.")
    cur.execute(
        """SELECT id,payload,effective_from,effective_to
           FROM configuration.config_versions
           WHERE company_id=%s AND config_type=%s AND config_key=%s
             AND status='APPROVED'
             AND effective_from<=%s
             AND (effective_to IS NULL OR effective_to>=%s)
           ORDER BY version_no DESC
           FOR SHARE""",
        (int(company_id), BABY_CONE_PROFILE_CONFIG_TYPE, key, effective_on, effective_on),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise RuntimeError("Multiple approved Baby Cone measurement profiles are effective for this date.")
    if not rows:
        raise ValueError("No approved Baby Cone measurement profile is effective for this variant and date.")
    from .configuration_service import validate_configuration_payload
    row = dict(rows[0])
    payload = validate_configuration_payload(BABY_CONE_PROFILE_CONFIG_TYPE, dict(row["payload"]))
    if str(payload["profile_code"]).strip().upper() == "":
        raise ValueError("Approved Baby Cone measurement profile code is missing.")
    if str(payload["variant_code"]).strip().upper() != variant:
        raise ValueError("Approved measurement profile does not match the selected Baby Cone variant.")
    if payload["method"] != "weight_per_length":
        raise ValueError("Baby Cone requires a weight_per_length measurement profile.")
    if not payload["active"]:
        raise ValueError("The approved Baby Cone measurement profile is inactive.")
    return {
        "config_type": BABY_CONE_PROFILE_CONFIG_TYPE,
        "config_key": key,
        "configuration_version_id": int(row["id"]),
        "source": "APPROVED_VERSION",
        "effective_on": effective_on,
        "payload": payload,
    }


def insert_baby_cone_measurement_profile_snapshot(
    cur, *, company_id: int, baby_cone_output_line_id: int, user_id: int,
    snapshot: dict[str, Any],
) -> None:
    """Pin the approved profile beside a Baby Cone DRAFT output line."""
    cur.execute(
        """INSERT INTO production.baby_cone_configuration_snapshots
           (company_id,baby_cone_output_line_id,config_type,config_key,
            configuration_version_id,source,effective_on,payload_snapshot,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (
            int(company_id), int(baby_cone_output_line_id), snapshot["config_type"],
            snapshot["config_key"], snapshot["configuration_version_id"],
            snapshot["source"], snapshot["effective_on"],
            Jsonb(snapshot["payload"]), int(user_id),
        ),
    )


def save_baby_cone_measurement_draft(
    cur, *, company_id: int, baby_cone_output_line_id: int,
    configuration_snapshot_id: int, user_id: int,
    gross_weight_grams: Any, empty_core_tare_grams: Any,
    measured_yards: Any, operator_code: str | None,
    required_yards: Any | None = None,
) -> dict[str, Any]:
    """Save or revise one measurement while its parent Baby Cone order is DRAFT."""
    from .baby_cone_measurement_service import calculate_baby_cone_profile_measurement

    cur.execute(
        """SELECT s.id,s.config_type,s.configuration_version_id,s.source,
                  s.effective_on,s.payload_snapshot,
                  o.company_id AS order_company_id,o.status AS order_status,
                  v.variant_code
           FROM production.baby_cone_configuration_snapshots s
           JOIN production.baby_cone_output_lines l
             ON l.id=s.baby_cone_output_line_id
           JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
           JOIN master.item_variants v ON v.id=l.item_variant_id
           WHERE s.id=%s AND s.baby_cone_output_line_id=%s
             AND s.company_id=%s
           FOR SHARE OF s,l,o""",
        (int(configuration_snapshot_id), int(baby_cone_output_line_id), int(company_id)),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError("The approved Baby Cone measurement snapshot/output line was not found.")
    row = dict(row)
    if int(row["order_company_id"]) != int(company_id):
        raise ValueError("Baby Cone measurement company mismatch.")
    if row["order_status"] != "DRAFT":
        raise ValueError("Baby Cone measurements can only be saved while the order is DRAFT.")
    if row["config_type"] != "MEASUREMENT_PROFILE" or row["source"] != "APPROVED_VERSION":
        raise ValueError("Baby Cone measurement requires an approved profile snapshot.")
    payload = dict(row["payload_snapshot"])
    if str(payload.get("variant_code", "")).strip().upper() != str(row["variant_code"]).strip().upper():
        raise ValueError("Pinned measurement profile does not match the Baby Cone output variant.")
    snapshot = {
        "config_type": row["config_type"],
        "configuration_version_id": int(row["configuration_version_id"]),
        "payload": payload,
    }
    result = calculate_baby_cone_profile_measurement(
        snapshot,
        gross_weight_grams=gross_weight_grams,
        empty_core_tare_grams=empty_core_tare_grams,
        measured_yards=measured_yards,
        operator_code=operator_code,
        required_yards=required_yards,
    )
    cur.execute(
        """INSERT INTO production.baby_cone_measurements
           (company_id,baby_cone_output_line_id,configuration_snapshot_id,
            gross_weight_grams,empty_core_tare_grams,net_yarn_grams,
            measured_yards,grams_per_yard,required_yards,required_yarn_kg,
            operator_code,requires_approval,created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (baby_cone_output_line_id) DO UPDATE SET
             configuration_snapshot_id=EXCLUDED.configuration_snapshot_id,
             gross_weight_grams=EXCLUDED.gross_weight_grams,
             empty_core_tare_grams=EXCLUDED.empty_core_tare_grams,
             net_yarn_grams=EXCLUDED.net_yarn_grams,
             measured_yards=EXCLUDED.measured_yards,
             grams_per_yard=EXCLUDED.grams_per_yard,
             required_yards=EXCLUDED.required_yards,
             required_yarn_kg=EXCLUDED.required_yarn_kg,
             operator_code=EXCLUDED.operator_code,
             requires_approval=EXCLUDED.requires_approval,
             created_by=EXCLUDED.created_by,
             updated_at=CURRENT_TIMESTAMP
           RETURNING id""",
        (
            int(company_id), int(baby_cone_output_line_id), int(configuration_snapshot_id),
            result["gross_weight_grams"], result["empty_core_tare_grams"],
            result["net_yarn_grams"], result["measured_yards"],
            result["grams_per_yard"], result.get("required_yards"),
            result.get("required_yarn_kg"), result.get("operator_code"),
            result["requires_approval"], int(user_id),
        ),
    )
    saved = cur.fetchone()
    return {"measurement_id": int(saved["id"]), **result}


PROCESS_ROUTE_CONFIG_TYPE = "PROCESS_ROUTE"


def validate_process_route_payload(payload: dict[str, Any], *, config_key: str) -> dict[str, Any]:
    """Validate an approved route against continuity and ARE's Nalki source rule."""
    from .configuration_rules import ProcessRoute

    key = str(config_key or "").strip().upper()
    if not key:
        raise ValueError("A process route configuration key is required.")
    route = ProcessRoute.model_validate(payload)
    normalized = route.model_dump(mode="json")
    if route.route_code.strip().upper() != key:
        raise ValueError("Process route code does not match its configuration key.")
    if not route.active:
        raise ValueError("The approved process route is inactive.")

    steps = route.steps
    for previous, current in zip(steps, steps[1:]):
        if previous.output_product_type.strip().casefold() != current.input_product_type.strip().casefold():
            raise ValueError("Process route is discontinuous: each step input must match the prior step output.")

    if route.product_type.strip().casefold() == "nalki":
        if any(step.input_product_type.strip().upper() == "BABY_CONE" for step in steps):
            raise ValueError("Nalki route cannot use Baby Cone as its input; Nalki must originate from Large Cone.")
        if not any(
            step.input_product_type.strip().upper() == "LARGE_CONE"
            and step.output_product_type.strip().upper() == "NALKI"
            for step in steps
        ):
            raise ValueError("Nalki route must include the Large Cone to Nalki process step.")
    return normalized


def resolve_process_route_snapshot(
    cur, *, company_id: int, effective_on: date, config_key: str,
) -> dict[str, Any]:
    """Resolve exactly one approved effective route; never invent a fallback route."""
    key = str(config_key or "").strip().upper()
    if not key:
        raise ValueError("A process route configuration key is required.")
    cur.execute(
        """SELECT id,payload,effective_from,effective_to
           FROM configuration.config_versions
           WHERE company_id=%s AND config_type=%s AND config_key=%s
             AND status='APPROVED' AND effective_from<=%s
             AND (effective_to IS NULL OR effective_to>=%s)
           ORDER BY version_no DESC FOR SHARE""",
        (int(company_id), PROCESS_ROUTE_CONFIG_TYPE, key, effective_on, effective_on),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise RuntimeError("Multiple approved process routes are effective for this date and key.")
    if not rows:
        raise ValueError("No approved process route is effective for this date and key.")
    row = dict(rows[0])
    normalized = validate_process_route_payload(dict(row["payload"]), config_key=key)
    # The JSON payload is an immutable copy of the approved version's terms.
    # Reject a payload whose effective period diverges from its DB governance columns.
    if normalized.get("effective_from") != row.get("effective_from").isoformat():
        raise ValueError("Process route payload effective date does not match its approved version.")
    payload_to = normalized.get("effective_to")
    row_to = row.get("effective_to")
    expected_to = row_to.isoformat() if row_to is not None else None
    if payload_to != expected_to:
        raise ValueError("Process route payload end date does not match its approved version.")
    return {
        "config_type": PROCESS_ROUTE_CONFIG_TYPE,
        "config_key": key,
        "configuration_version_id": int(row["id"]),
        "source": "APPROVED_VERSION",
        "effective_on": effective_on,
        "payload": normalized,
    }


OWNERSHIP_POLICY_CONFIG_TYPE = "OWNERSHIP_POLICY"


def validate_ownership_policy_payload(payload: dict[str, Any], *, config_key: str) -> dict[str, Any]:
    """Validate ownership permissions; PARTY requires approval and locked-rate controls."""
    from .configuration_rules import OwnershipPolicy

    key = str(config_key or "").strip().upper()
    if not key:
        raise ValueError("An ownership policy configuration key is required.")
    policy = OwnershipPolicy.model_validate(payload)
    normalized = policy.model_dump(mode="json")
    expected_key = policy.product_type.strip().upper().replace(" ", "-") + "-OWNERSHIP"
    if key != expected_key:
        raise ValueError("Ownership policy key must match its product type.")
    if "PARTY" in policy.allowed_owners:
        if not policy.party_rate_required:
            raise ValueError("PARTY ownership requires a locked party rate.")
        if not policy.party_stock_requires_approval:
            raise ValueError("PARTY ownership requires a separate approval workflow.")
    return normalized


def resolve_ownership_policy_snapshot(
    cur, *, company_id: int, effective_on: date, config_key: str,
) -> dict[str, Any]:
    """Resolve exactly one approved effective ownership policy; never default PARTY on."""
    key = str(config_key or "").strip().upper()
    if not key:
        raise ValueError("An ownership policy configuration key is required.")
    cur.execute(
        """SELECT id,payload,effective_from,effective_to
           FROM configuration.config_versions
           WHERE company_id=%s AND config_type=%s AND config_key=%s
             AND status='APPROVED' AND effective_from<=%s
             AND (effective_to IS NULL OR effective_to>=%s)
           ORDER BY version_no DESC FOR SHARE""",
        (int(company_id), OWNERSHIP_POLICY_CONFIG_TYPE, key, effective_on, effective_on),
    )
    rows = cur.fetchall()
    if len(rows) > 1:
        raise RuntimeError("Multiple approved ownership policies are effective for this date and key.")
    if not rows:
        raise ValueError("No approved ownership policy is effective for this date and key.")
    row = dict(rows[0])
    payload = validate_ownership_policy_payload(dict(row["payload"]), config_key=key)
    return {
        "config_type": OWNERSHIP_POLICY_CONFIG_TYPE,
        "config_key": key,
        "configuration_version_id": int(row["id"]),
        "source": "APPROVED_VERSION",
        "effective_on": effective_on,
        "payload": payload,
    }
