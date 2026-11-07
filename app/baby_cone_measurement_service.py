"""Pure Baby Cone measurement arithmetic; no database or stock side effects."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


def _positive_decimal(value: Any, label: str, *, allow_zero: bool = False) -> Decimal:
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError, AttributeError) as exc:
        raise ValueError(f"{label} must be a valid number.") from exc
    if not number.is_finite() or (number < 0 if allow_zero else number <= 0):
        qualifier = "zero or greater" if allow_zero else "greater than zero"
        raise ValueError(f"{label} must be finite and {qualifier}.")
    return number


def calculate_baby_cone_measurement(
    gross_weight_grams: Any,
    empty_core_tare_grams: Any,
    measured_yards: Any,
    required_yards: Any | None = None,
) -> dict[str, Decimal]:
    """Calculate net yarn, grams/yard and optional kg required for target yards.

    This is calculation-only. It deliberately does not resolve/activate rules,
    save measurements, reserve material, post stock, or calculate production cost.
    """
    gross = _positive_decimal(gross_weight_grams, "Gross weight")
    tare = _positive_decimal(empty_core_tare_grams, "Empty-core tare", allow_zero=True)
    yards = _positive_decimal(measured_yards, "Measured yards")
    if gross <= tare:
        raise ValueError("Gross weight must exceed empty-core tare weight.")

    net = gross - tare
    grams_per_yard = net / yards
    result = {
        "gross_weight_grams": gross,
        "empty_core_tare_grams": tare,
        "net_yarn_grams": net,
        "measured_yards": yards,
        "grams_per_yard": grams_per_yard,
    }
    if required_yards is not None:
        target_yards = _positive_decimal(required_yards, "Required yards")
        result["required_yards"] = target_yards
        result["required_yarn_kg"] = (grams_per_yard * target_yards) / Decimal("1000")
    return result


def calculate_baby_cone_profile_measurement(
    profile_snapshot: dict[str, Any],
    *,
    gross_weight_grams: Any,
    empty_core_tare_grams: Any,
    measured_yards: Any,
    operator_code: str | None,
    required_yards: Any | None = None,
) -> dict[str, Any]:
    """Calculate a measurement only against a resolved approved profile snapshot.

    Approval is returned as a required workflow flag; this function never approves,
    saves, reserves, posts, or calculates cost.
    """
    if not isinstance(profile_snapshot, dict):
        raise ValueError("An approved measurement profile snapshot is required.")
    if profile_snapshot.get("config_type") != "MEASUREMENT_PROFILE":
        raise ValueError("Unsupported configuration snapshot for Baby Cone measurement.")
    version_id = profile_snapshot.get("configuration_version_id")
    if not isinstance(version_id, int) or version_id <= 0:
        raise ValueError("The approved measurement profile version is missing.")
    payload = profile_snapshot.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Measurement profile payload is missing.")
    if payload.get("method") != "weight_per_length" or payload.get("active") is not True:
        raise ValueError("An active weight_per_length profile is required.")
    variant_code = str(payload.get("variant_code") or "").strip().upper()
    profile_code = str(payload.get("profile_code") or "").strip().upper()
    if not variant_code or not profile_code:
        raise ValueError("Measurement profile and variant codes are required.")
    operator = str(operator_code or "").strip()
    if payload.get("requires_operator", True) and not operator:
        raise ValueError("This measurement profile requires an operator.")
    result = calculate_baby_cone_measurement(
        gross_weight_grams, empty_core_tare_grams, measured_yards, required_yards
    )
    return {
        **result,
        "configuration_version_id": version_id,
        "profile_code": profile_code,
        "variant_code": variant_code,
        "operator_code": operator or None,
        "requires_approval": bool(payload.get("requires_approval", False)),
        "tolerance_percent": _positive_decimal(
            payload.get("tolerance_percent", "0"), "Profile tolerance", allow_zero=True
        ),
    }


def get_baby_cone_measurement_draft_options(company_id: int) -> list[dict[str, Any]]:
    """List only DRAFT output lines with a pinned approved measurement profile."""
    from .db import get_connection
    with get_connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
                cur.execute(
                    """SELECT l.id AS output_line_id,o.baby_cone_no,o.baby_cone_date,
                              v.variant_code,v.variant_name,s.id AS configuration_snapshot_id,
                              s.payload_snapshot->>'profile_code' AS profile_code,
                              s.configuration_version_id
                       FROM production.baby_cone_output_lines l
                       JOIN production.baby_cone_orders o ON o.id=l.baby_cone_order_id
                       JOIN master.item_variants v ON v.id=l.item_variant_id
                       JOIN production.baby_cone_configuration_snapshots s
                         ON s.baby_cone_output_line_id=l.id
                       WHERE o.company_id=%s AND o.status='DRAFT'
                         AND s.config_type='MEASUREMENT_PROFILE'
                         AND s.source='APPROVED_VERSION'
                       ORDER BY o.baby_cone_date DESC,o.id DESC,l.line_no""",
                    (int(company_id),),
                )
                return [dict(row) for row in cur.fetchall()]
