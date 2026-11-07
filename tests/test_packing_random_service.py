import unittest
from decimal import Decimal

from app.packing_random_service import (
    RANDOM_SOURCE_FRESH,
    RANDOM_SOURCE_PARTY_REJECTED_USABLE,
    validate_random_100_allocations,
)


def allocations(boxes=2):
    return [
        {
            "item_variant_id": i,
            "brand_id": 1 if i <= 50 else 2,
            "shade_id": i,
            "source_type": RANDOM_SOURCE_FRESH,
            "source_table": "production.nalki_output_lines",
            "output_type": "GOOD",
            "quality_status": "ACCEPTED",
            "stock_verified": True,
            "source_line_id": i,
            "quantity_pieces": boxes,
            "available_pieces": boxes + 1,
            "ownership_type_id": 1,
            "owner_party_id": None,
            "unit_cost": "2.50",
            "batch_id": 1000 + i,
        }
        for i in range(1, 101)
    ]


class RandomPackingRulesTests(unittest.TestCase):
    def test_accepts_100_unique_shades_and_mixed_brands(self):
        result = validate_random_100_allocations(allocations(), 2)
        self.assertEqual(len(result), 100)
        self.assertEqual(result[0]["total_source_cost"], Decimal("5.00"))
        self.assertEqual({x["brand_id"] for x in result}, {1, 2})

    def test_party_rejected_sources_can_be_captured_in_draft_pending_approval(self):
        rows = allocations(1)
        rows[0].update({
            "source_type": RANDOM_SOURCE_PARTY_REJECTED_USABLE,
            "source_table": "production.outside_labeling_return_lines",
            "return_status": "ACCEPTED",
            "quality_status": "ACCEPTED",
            "source_nalki_line_id": 7001,
            "source_line_id": 9001,
            "ownership_type_id": 2,
            "owner_party_id": 77,
        })
        result = validate_random_100_allocations(rows, 1)
        self.assertEqual(result[0]["ownership_type_id"], 2)
        self.assertEqual(result[0]["owner_party_id"], 77)

    def test_rejected_usable_requires_accepted_return_and_quality(self):
        rows = allocations(1)
        rows[0].update({
            "source_type": RANDOM_SOURCE_PARTY_REJECTED_USABLE,
            "source_table": "production.outside_labeling_return_lines",
            "return_status": "REJECTED",
            "quality_status": "REJECTED",
            "source_nalki_line_id": 7001,
            "ownership_type_id": 2,
            "owner_party_id": 77,
        })
        with self.assertRaisesRegex(ValueError, "both ACCEPTED"):
            validate_random_100_allocations(rows, 1)

    def test_source_table_is_allow_listed_and_stock_must_be_verified(self):
        rows = allocations(1)
        rows[0]["source_table"] = "inventory.stock_balances"
        with self.assertRaisesRegex(ValueError, "approved production source table"):
            validate_random_100_allocations(rows, 1)
        rows = allocations(1)
        rows[0]["stock_verified"] = False
        with self.assertRaisesRegex(ValueError, "stock balance verified"):
            validate_random_100_allocations(rows, 1)

    def test_party_rejected_return_requires_original_nalki_lineage(self):
        rows = allocations(1)
        rows[0].update({
            "source_type": RANDOM_SOURCE_PARTY_REJECTED_USABLE,
            "source_table": "production.outside_labeling_return_lines",
            "return_status": "ACCEPTED",
            "quality_status": "ACCEPTED",
            "source_nalki_line_id": None,
            "ownership_type_id": 2,
            "owner_party_id": 77,
        })
        with self.assertRaisesRegex(ValueError, "original outside-labeling Nalki source line"):
            validate_random_100_allocations(rows, 1)

    def test_party_stock_is_preserved_as_party_in_draft_validation(self):
        rows = allocations(1)
        rows[0].update({
            "source_type": RANDOM_SOURCE_PARTY_REJECTED_USABLE,
            "source_table": "production.outside_labeling_return_lines",
            "return_status": "ACCEPTED",
            "quality_status": "ACCEPTED",
            "source_nalki_line_id": 7001,
            "ownership_type_id": 2,
            "owner_party_id": 77,
        })
        result = validate_random_100_allocations(rows, 1)
        self.assertEqual(result[0]["ownership_type_id"], 2)
        self.assertEqual(result[0]["owner_party_id"], 77)

    def test_party_ownership_requires_owner_party_and_own_has_none(self):
        rows = allocations(1)
        rows[0].update({"ownership_type_id": 2, "owner_party_id": None})
        with self.assertRaisesRegex(ValueError, "retain its owner party"):
            validate_random_100_allocations(rows, 1)
        rows = allocations(1)
        rows[0].update({"ownership_type_id": 1, "owner_party_id": 77})
        with self.assertRaisesRegex(ValueError, "OWN stock cannot"):
            validate_random_100_allocations(rows, 1)

    def test_requires_exactly_100_unique_shades(self):
        rows = allocations(1)
        rows[-1]["shade_id"] = rows[0]["shade_id"]
        with self.assertRaisesRegex(ValueError, "exactly 100 unique"):
            validate_random_100_allocations(rows, 1)

    def test_each_shade_must_supply_one_piece_per_finished_box(self):
        rows = allocations(2)
        rows[0]["quantity_pieces"] = 1
        with self.assertRaisesRegex(ValueError, "exactly one piece per finished random box"):
            validate_random_100_allocations(rows, 2)

    def test_rejects_duplicate_source_line_and_insufficient_source(self):
        rows = allocations(1)
        rows[1]["source_line_id"] = rows[0]["source_line_id"]
        with self.assertRaisesRegex(ValueError, "duplicate source line"):
            validate_random_100_allocations(rows, 1)
        rows = allocations(1)
        rows[0]["available_pieces"] = 0
        with self.assertRaisesRegex(ValueError, "within source availability"):
            validate_random_100_allocations(rows, 1)

    def test_existing_source_cost_is_carried_not_recomputed(self):
        rows = allocations(3)
        rows[0]["unit_cost"] = "0.125"
        result = validate_random_100_allocations(rows, 3)
        self.assertEqual(result[0]["unit_cost"], Decimal("0.125"))
        self.assertEqual(result[0]["total_source_cost"], Decimal("0.375"))

    def test_numeric_database_piece_quantities_accept_integral_scale(self):
        rows = allocations(1)
        rows[0]["available_pieces"] = "3.000000"
        result = validate_random_100_allocations(rows, 1)
        self.assertEqual(result[0]["available_pieces"], 3)
        rows = allocations(1)
        rows[0]["available_pieces"] = "3.500000"
        with self.assertRaisesRegex(ValueError, "whole number of pieces"):
            validate_random_100_allocations(rows, 1)


if __name__ == "__main__":
    unittest.main()

