"""Pure validation rules for the separate random 100-piece Nalki packing workflow.

This module deliberately has no database writes or route integration. Source-line
availability and stock posting remain disabled until rejected-return source semantics
and the production lineage are wired and verified.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

RANDOM_SOURCE_FRESH = "FRESH_NALKI"
RANDOM_SOURCE_PARTY_REJECTED_USABLE = "PARTY_REJECTED_USABLE"
RANDOM_ALLOWED_SOURCES = frozenset({
    RANDOM_SOURCE_FRESH,
    RANDOM_SOURCE_PARTY_REJECTED_USABLE,
})

SOURCE_TABLE_BY_TYPE = {
    RANDOM_SOURCE_FRESH: "production.nalki_output_lines",
    RANDOM_SOURCE_PARTY_REJECTED_USABLE: "production.outside_labeling_return_lines",
}


def validate_random_source_evidence(line: dict[str, Any]) -> None:
    """Require database-derived source evidence; caller flags alone are not proof."""
    source_type = str(line.get("source_type", "")).strip().upper()
    source_table = str(line.get("source_table", "")).strip().lower()
    expected_table = SOURCE_TABLE_BY_TYPE.get(source_type)
    if expected_table is None or source_table != expected_table:
        raise ValueError("Random packing source must reference its approved production source table.")
    if line.get("stock_verified") is not True:
        raise ValueError("Random packing source must have its OWN/PARTY stock balance verified from the database.")
    if source_type == RANDOM_SOURCE_FRESH:
        if str(line.get("output_type", "")).upper() != "GOOD" or str(line.get("quality_status", "")).upper() != "ACCEPTED":
            raise ValueError("Fresh Nalki source must be GOOD output with ACCEPTED quality.")
    else:
        if str(line.get("return_status", "")).upper() != "ACCEPTED" or str(line.get("quality_status", "")).upper() != "ACCEPTED":
            raise ValueError("Party-rejected Nalki is eligible only when its return and quality statuses are both ACCEPTED.")
        if line.get("source_nalki_line_id") in (None, ""):
            raise ValueError("Party-rejected usable return must retain its original outside-labeling Nalki source line.")
        if int(line.get("ownership_type_id", 0)) != 2 or line.get("owner_party_id") in (None, ""):
            raise ValueError("Party-rejected usable return must retain PARTY ownership and its owner.")


def _whole_number(value: Any, field: str) -> int:
    number = _decimal(value, field)
    if number < 0 or number != number.to_integral_value():
        raise ValueError(f"{field} must be a non-negative whole number of pieces.")
    return int(number)


def _decimal(value: Any, field: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a valid number.")
    if not result.is_finite():
        raise ValueError(f"{field} must be finite.")
    return result


def validate_random_100_allocations(
    lines: list[dict[str, Any]],
    finished_boxes_qty: Any,
) -> list[dict[str, Any]]:
    """Validate 100 unique shades and preserve each source/ownership/cost allocation.

    Fresh Nalki and party-rejected-but-usable Nalki may be mixed. Rejected stock is
    optional, never prioritized, and is never reclassified as wastage. The random
    workflow does not impose a single-brand rule. Every finished box consumes one
    piece of each of 100 unique shade IDs. If a shade is supplied by multiple source
    lines, their allocated quantities must sum to the finished-box count.
    """
    try:
        boxes = int(str(finished_boxes_qty).strip())
    except (TypeError, ValueError):
        raise ValueError("Finished random-box quantity must be a positive whole number.")
    if boxes <= 0 or boxes > 100000:
        raise ValueError("Finished random-box quantity must be a positive whole number.")
    if not isinstance(lines, list) or not lines:
        raise ValueError("Random 100 workflow requires source allocations for 100 unique shades.")

    normalized: list[dict[str, Any]] = []
    shade_totals: dict[int, int] = {}
    source_keys: set[tuple[str, int]] = set()
    shade_brands: dict[int, set[int]] = {}

    for index, line in enumerate(lines, start=1):
        variant_id = _whole_number(line.get("item_variant_id"), f"Source allocation {index} variant ID")
        shade_id = _whole_number(line.get("shade_id"), f"Source allocation {index} shade ID")
        brand_id = _whole_number(line.get("brand_id"), f"Source allocation {index} brand ID")
        source_line_id = _whole_number(line.get("source_line_id"), f"Source allocation {index} source-line ID")
        ownership_type_id = _whole_number(line.get("ownership_type_id"), f"Source allocation {index} ownership ID")
        quantity = _whole_number(line.get("quantity_pieces"), f"Source allocation {index} quantity")
        available = _whole_number(line.get("available_pieces"), f"Source allocation {index} availability")

        source_type = str(line.get("source_type", "")).strip().upper()
        validate_random_source_evidence(line)
        owner_party_raw = line.get("owner_party_id")
        try:
            owner_party_id = int(str(owner_party_raw).strip()) if owner_party_raw not in (None, "") else None
        except (TypeError, ValueError):
            raise ValueError(f"Source allocation {index}: owner party ID must be numeric.")
        unit_cost = _decimal(line.get("unit_cost"), f"Source allocation {index} unit cost")

        if min(variant_id, shade_id, brand_id, source_line_id) <= 0:
            raise ValueError(f"Source allocation {index}: master and source-line IDs must be positive.")
        if source_type not in RANDOM_ALLOWED_SOURCES:
            raise ValueError(f"Source allocation {index}: unsupported random-packing source.")
        if ownership_type_id not in (1, 2):
            raise ValueError(f"Source allocation {index}: ownership must remain OWN or PARTY.")
        if ownership_type_id == 1 and owner_party_id is not None:
            raise ValueError(f"Source allocation {index}: OWN stock cannot carry an owner party.")
        if ownership_type_id == 2 and (owner_party_id is None or owner_party_id <= 0):
            raise ValueError(f"Source allocation {index}: PARTY stock must retain its owner party.")
        # PARTY is permitted on a DRAFT only; parent status-transition guards
        # require a separately approved request and locked rate before advance.
        if quantity <= 0 or available < quantity:
            raise ValueError(f"Source allocation {index}: allocated quantity must be positive and within source availability.")
        if unit_cost < 0:
            raise ValueError(f"Source allocation {index}: existing source cost cannot be negative.")
        source_key = (source_type, source_line_id)
        if source_key in source_keys:
            raise ValueError(f"Source allocation {index}: duplicate source line; combine its allocation.")
        source_keys.add(source_key)
        shade_totals[shade_id] = shade_totals.get(shade_id, 0) + quantity
        shade_brands.setdefault(shade_id, set()).add(brand_id)
        normalized.append({
            "item_variant_id": variant_id,
            "brand_id": brand_id,
            "shade_id": shade_id,
            "source_type": source_type,
            "source_table": line["source_table"],
            "source_line_id": source_line_id,
            "quantity_pieces": quantity,
            "available_pieces": available,
            "ownership_type_id": ownership_type_id,
            "owner_party_id": owner_party_id,
            "unit_cost": unit_cost,
            "total_source_cost": unit_cost * quantity,
            "batch_id": line.get("batch_id"),
            "is_usable_rejected": source_type == RANDOM_SOURCE_PARTY_REJECTED_USABLE,
        })

    if len(shade_totals) != 100:
        raise ValueError("Each random 100-piece box requires exactly 100 unique shade IDs.")
    if any(total != boxes for total in shade_totals.values()):
        raise ValueError(
            "Every unique shade must contribute exactly one piece per finished random box; "
            "source allocations for each shade must equal the finished-box quantity."
        )
    if any(len(brands) != 1 for brands in shade_brands.values()):
        raise ValueError("A single shade cannot be sourced from conflicting brand variants.")

    return normalized
