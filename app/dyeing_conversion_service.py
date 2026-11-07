"""DRAFT-only, approved and directional Dyeing unit-conversion snapshots."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from .unit_conversion_service import (
    convert_unit_quantity,
    resolve_approved_unit_conversion,
)


def build_dyeing_unit_conversion_snapshot(
    cur, *, company_id: int, effective_on: date,
    source_quantity: Decimal, source_unit_code: str,
    target_unit_code: str, target_decimal_places: int,
) -> dict:
    """Build immutable evidence; never guess, reverse, or post a conversion."""
    source_code = str(source_unit_code or "").strip().upper()
    target_code = str(target_unit_code or "").strip().upper()
    quantity = Decimal(str(source_quantity))
    if not source_code or not target_code:
        raise ValueError("Source and base unit codes are required.")
    if not quantity.is_finite() or quantity <= 0:
        raise ValueError("Source quantity must be finite and greater than zero.")
    if int(target_decimal_places) < 0 or int(target_decimal_places) > 6:
        raise ValueError("Base-unit precision must be between 0 and 6 decimal places.")

    if source_code == target_code:
        return {
            "status": "NOT_REQUIRED",
            "effective_on": effective_on,
            "source_unit_code": source_code,
            "target_unit_code": target_code,
            "source_quantity": quantity,
            "converted_quantity": quantity,
            "conversion_factor": Decimal("1"),
            "rounding_places": None,
            "rounding_mode": "ROUND_HALF_UP",
            "configuration_version_id": None,
            "snapshot": {
                "status": "NOT_REQUIRED",
                "source": "SAME_BASE_UNIT",
                "source_unit_code": source_code,
                "target_unit_code": target_code,
                "source_quantity": str(quantity),
                "converted_quantity": str(quantity),
                "factor": "1",
                "rounding_mode": "ROUND_HALF_UP",
                "effective_on": effective_on.isoformat(),
                "configuration_version_id": None,
            },
        }

    try:
        rule = resolve_approved_unit_conversion(
            cur, company_id=int(company_id),
            from_unit_code=source_code, to_unit_code=target_code,
            effective_on=effective_on,
        )
    except ValueError as exc:
        if not str(exc).startswith("No approved effective unit conversion exists for "):
            raise
        return {
            "status": "PENDING_CONFIGURATION",
            "effective_on": effective_on,
            "source_unit_code": source_code,
            "target_unit_code": target_code,
            "source_quantity": quantity,
            "converted_quantity": None,
            "conversion_factor": None,
            "rounding_places": None,
            "rounding_mode": "ROUND_HALF_UP",
            "configuration_version_id": None,
            "snapshot": {
                "status": "PENDING_CONFIGURATION",
                "source": "NO_APPROVED_EFFECTIVE_RULE",
                "source_unit_code": source_code,
                "target_unit_code": target_code,
                "source_quantity": str(quantity),
                "converted_quantity": None,
                "rounding_mode": "ROUND_HALF_UP",
                "effective_on": effective_on.isoformat(),
                "configuration_version_id": None,
                "reason": str(exc),
            },
        }

    version_id = int(rule["configuration_version_id"])
    factor = Decimal(str(rule["factor"]))
    places = int(rule["rounding_places"])
    common = {
        "effective_on": effective_on,
        "source_unit_code": source_code,
        "target_unit_code": target_code,
        "source_quantity": quantity,
        "conversion_factor": factor,
        "rounding_places": places,
        "rounding_mode": "ROUND_HALF_UP",
        "configuration_version_id": version_id,
    }
    try:
        result = convert_unit_quantity(
            quantity, rule, max_quantity_places=int(target_decimal_places)
        )
    except ValueError as exc:
        if "target quantity precision" not in str(exc):
            raise
        unrounded = quantity * factor
        snapshot = {
            "status": "BLOCKED_PRECISION",
            "source": "APPROVED_VERSION",
            "source_unit_code": source_code,
            "target_unit_code": target_code,
            "source_quantity": str(quantity),
            "unrounded_target_quantity": str(unrounded),
            "converted_quantity": None,
            "factor": str(factor),
            "rounding_places": places,
            "rounding_mode": "ROUND_HALF_UP",
            "effective_on": effective_on.isoformat(),
            "configuration_version_id": version_id,
            "reason": str(exc),
        }
        return {
            **common, "status": "BLOCKED_PRECISION",
            "converted_quantity": None, "snapshot": snapshot,
        }

    snapshot = {
        "status": "APPROVED",
        "source": "APPROVED_VERSION",
        "source_unit_code": source_code,
        "target_unit_code": target_code,
        "source_quantity": str(quantity),
        "unrounded_target_quantity": str(result["unrounded_target_quantity"]),
        "converted_quantity": str(result["target_quantity"]),
        "factor": str(factor),
        "rounding_places": places,
        "rounding_mode": "ROUND_HALF_UP",
        "rounding_difference": str(result["rounding_difference"]),
        "effective_on": effective_on.isoformat(),
        "configuration_version_id": version_id,
        "configuration": rule["payload"],
    }
    return {
        **common, "status": "APPROVED",
        "converted_quantity": result["target_quantity"],
        "snapshot": snapshot,
    }
