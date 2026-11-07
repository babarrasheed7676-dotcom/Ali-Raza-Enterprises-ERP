"""Rule-based, read-only dashboard assistant.

This module intentionally has no language-model client and never constructs SQL.
It delegates only to existing, reviewed SELECT-only inventory helpers.
"""
from decimal import Decimal
import re
from typing import Any

from .db import get_dashboard_inventory_summary, get_inventory_stock

MAX_QUESTION_LENGTH = 120
MAX_RESULTS = 8


def _money(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _stock_row(row: dict) -> dict:
    """Return a small JSON-safe stock row; do not expose internal database fields."""
    return {
        "item_code": str(row.get("item_code") or ""),
        "item_name": str(row.get("item_name") or ""),
        "variant_code": str(row.get("variant_code") or ""),
        "variant_name": str(row.get("variant_name") or ""),
        "brand_name": str(row.get("brand_name") or ""),
        "shade_code": str(row.get("shade_code") or ""),
        "shade_name": str(row.get("shade_name") or ""),
        "location_name": str(row.get("location_name") or ""),
        "ownership_name": str(row.get("ownership_name") or ""),
        "party_name": str(row.get("party_name") or ""),
        "quantity": _money(row.get("quantity")),
        "unit_code": str(row.get("unit_code") or ""),
        "total_value": _money(row.get("total_value")),
    }


def answer_inventory_question(question: str) -> dict:
    """Answer a small allowlist of inventory questions using read-only helpers."""
    question = (question or "").strip()
    if not question:
        return {
            "kind": "help",
            "message": "Ask about total stock value, stock value by location, or search for an item, variant, shade or party.",
            "rows": [],
            "locations": [],
        }
    if len(question) > MAX_QUESTION_LENGTH:
        return {
            "kind": "help",
            "message": f"Please keep the question to {MAX_QUESTION_LENGTH} characters or fewer.",
            "rows": [],
            "locations": [],
        }

    normalized = re.sub(r"\s+", " ", question.casefold()).strip()
    if normalized in {"help", "examples", "what can you do", "madad"}:
        return {
            "kind": "help",
            "message": "Try: ‘total stock value’, ‘stock by location’, or type an item code, item name, variant, shade or party name. I only answer from read-only inventory data.",
            "rows": [],
            "locations": [],
        }

    location_terms = (
        "by location", "location wise", "location-wise", "locations",
        "stock location", "store wise", "godown", "stock kahan",
    )
    is_location_question = any(term in normalized for term in location_terms)

    total_terms = (
        "total stock", "stock value", "inventory value", "overall stock",
        "total inventory", "kul stock", "stock ki total", "kul inventory",
    )
    if any(term in normalized for term in total_terms) and not is_location_question:
        summary = get_dashboard_inventory_summary()
        return {
            "kind": "summary",
            "message": "Current recorded inventory summary (read-only). This is stock valuation, not profit or cash balance.",
            "summary": {
                "total_stock_value": _money(summary.get("total_stock_value")),
                "active_variants": int(summary.get("active_variants") or 0),
                "stock_locations": int(summary.get("stock_locations") or 0),
            },
            "rows": [],
            "locations": [],
        }

    if is_location_question:
        summary = get_dashboard_inventory_summary()
        locations = [
            {
                "location_name": str(row.get("location_name") or ""),
                "stock_value": _money(row.get("stock_value")),
                "variant_count": int(row.get("variant_count") or 0),
            }
            for row in summary.get("locations", [])
        ]
        return {
            "kind": "locations",
            "message": "Recorded stock value grouped by location. Values come from current inventory balances.",
            "locations": locations,
            "rows": [],
        }

    # Remove common request phrasing before searching known item/variant/shade/party fields.
    search_term = re.sub(
        r"^(please\s+)?(?:(?:show\s+)?stock\s+(?:for|of)\s+|(?:show|find|search|look up|item|search for)\s+)",
        "", question, flags=re.IGNORECASE,
    ).strip()
    if len(search_term) < 2:
        return {
            "kind": "help",
            "message": "Please enter at least two characters, or ask ‘total stock value’ / ‘stock by location’.",
            "rows": [],
            "locations": [],
        }

    rows = get_inventory_stock(search_term)
    if not rows:
        return {
            "kind": "search",
            "message": f"No matching inventory rows were found for ‘{search_term}’. Try an item code, item name, variant, shade or party name.",
            "rows": [],
            "locations": [],
        }
    return {
        "kind": "search",
        "message": f"The existing inventory lookup returned {len(rows)} row(s); showing up to {min(len(rows), MAX_RESULTS)}. Search is limited to known item, variant, shade and party fields (maximum 1,000 rows fetched).",
        "rows": [_stock_row(row) for row in rows[:MAX_RESULTS]],
        "locations": [],
    }