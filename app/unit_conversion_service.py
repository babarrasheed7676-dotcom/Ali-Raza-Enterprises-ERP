"""Approved, directional unit conversion resolution and safe Decimal arithmetic.

This module is intentionally not wired into stock posting yet. It provides
validated conversion evidence and deterministic calculations. Callers must pass
the target store precision explicitly; fine-unit conversion must not be posted
to a lower-precision stock ledger.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from .configuration_rules import UnitConversion


def unit_conversion_key(from_unit_code: str, to_unit_code: str) -> str:
    source = str(from_unit_code or "").strip().upper()
    target = str(to_unit_code or "").strip().upper()
    if not source or not target or source == target:
        raise ValueError("Unit conversion requires two different unit codes.")
    return f"{source}-TO-{target}"


def resolve_approved_unit_conversion(
    cur, *, company_id: int, from_unit_code: str, to_unit_code: str,
    effective_on: date,
) -> dict[str, Any]:
    """Resolve exactly one approved, company-scoped, date-effective directed rule."""
    key = unit_conversion_key(from_unit_code, to_unit_code)
    cur.execute(
        """SELECT id,config_key,payload,effective_from,effective_to
           FROM configuration.config_versions
           WHERE company_id=%s AND config_type='UNIT_CONVERSION'
             AND config_key=%s AND status='APPROVED'
             AND effective_from<=%s
             AND (effective_to IS NULL OR effective_to>=%s)
           ORDER BY version_no DESC
           FOR SHARE""",
        (int(company_id), key, effective_on, effective_on),
    )
    rows = cur.fetchall()
    if len(rows) != 1:
        if not rows:
            raise ValueError(f"No approved effective unit conversion exists for {key}.")
        raise RuntimeError(f"Multiple approved effective unit conversions exist for {key}.")

    row = dict(rows[0])
    rule = UnitConversion.model_validate(dict(row["payload"]))
    if not rule.active:
        raise ValueError(f"Approved unit conversion {key} is inactive.")
    if rule.from_unit_code.strip().upper() != str(from_unit_code).strip().upper():
        raise ValueError("Approved conversion source unit does not match the requested direction.")
    if rule.to_unit_code.strip().upper() != str(to_unit_code).strip().upper():
        raise ValueError("Approved conversion target unit does not match the requested direction.")
    if row["config_key"] != key:
        raise ValueError("Approved conversion key does not match its source and target units.")
    if rule.effective_from != row["effective_from"]:
        raise ValueError("Conversion payload effective date does not match its approved version.")
    if rule.effective_to != row.get("effective_to"):
        raise ValueError("Conversion payload end date does not match its approved version.")

    cur.execute(
        """SELECT code,unit_type FROM master.units
           WHERE code = ANY(%s) AND is_active=TRUE
           ORDER BY code
           FOR SHARE""",
        ([str(from_unit_code).strip().upper(), str(to_unit_code).strip().upper()],),
    )
    unit_rows = cur.fetchall()
    active_codes = {str(item["code"]).upper() for item in unit_rows}
    expected_codes = {
        str(from_unit_code).strip().upper(),
        str(to_unit_code).strip().upper(),
    }
    if active_codes != expected_codes:
        raise ValueError("Both source and target units must exist and be active.")
    unit_types = {str(item["unit_type"]).upper() for item in unit_rows}
    if len(unit_types) != 1:
        raise ValueError("Unit conversion source and target dimensions do not match.")

    return {
        "config_type": "UNIT_CONVERSION",
        "config_key": key,
        "configuration_version_id": int(row["id"]),
        "source": "APPROVED_VERSION",
        "effective_on": effective_on,
        "from_unit_code": rule.from_unit_code.strip().upper(),
        "to_unit_code": rule.to_unit_code.strip().upper(),
        "factor": rule.factor,
        "rounding_places": int(rule.rounding_places),
        "rounding_mode": "ROUND_HALF_UP",
        "payload": rule.model_dump(mode="json"),
    }


def convert_unit_quantity(
    quantity: Decimal | int | str, snapshot: dict[str, Any], *,
    max_quantity_places: int = 3,
) -> dict[str, Decimal | str | int]:
    """Convert source quantity to target quantity using pinned rule and explicit rounding."""
    try:
        source_quantity = Decimal(str(quantity))
        factor = Decimal(str(snapshot["factor"]))
        places = int(snapshot["rounding_places"])
    except (InvalidOperation, TypeError, ValueError, KeyError) as exc:
        raise ValueError("Quantity or conversion snapshot is invalid.") from exc
    if not source_quantity.is_finite() or source_quantity <= 0:
        raise ValueError("Source quantity must be a finite number greater than zero.")
    if not factor.is_finite() or factor <= 0:
        raise ValueError("Conversion factor must be a finite number greater than zero.")
    if places < 0 or places > 6 or places > int(max_quantity_places):
        raise ValueError(
            f"Conversion rounding precision exceeds the supported target quantity precision ({max_quantity_places})."
        )
    from_code = str(snapshot.get("from_unit_code") or "").strip().upper()
    to_code = str(snapshot.get("to_unit_code") or "").strip().upper()
    if not from_code or not to_code or from_code == to_code:
        raise ValueError("Conversion snapshot must identify two different units.")
    if snapshot.get("rounding_mode", "ROUND_HALF_UP") != "ROUND_HALF_UP":
        raise ValueError("Unsupported conversion rounding mode.")

    unrounded = source_quantity * factor
    quantum = Decimal(1).scaleb(-places)
    converted = unrounded.quantize(quantum, rounding=ROUND_HALF_UP)
    if converted <= 0:
        raise ValueError("Converted quantity rounds to zero; conversion is blocked.")
    return {
        "source_quantity": source_quantity,
        "source_unit_code": from_code,
        "factor": factor,
        "unrounded_target_quantity": unrounded,
        "target_quantity": converted,
        "target_unit_code": to_code,
        "rounding_places": places,
        "rounding_mode": "ROUND_HALF_UP",
        "rounding_difference": converted - unrounded,
    }