import unittest
from decimal import Decimal

from app.baby_cone_draft_service import _baby_cone_source_rows


def _source(**overrides):
    row = {
        "source_output_line_id": 31,
        "big_cone_order_id": 8,
        "big_cone_no": "BC-20261107-0001",
        "big_cone_date": "2026-11-07",
        "line_no": 1,
        "item_code": "YARN",
        "item_name": "Yarn",
        "variant_code": "PC-30",
        "batch_no": "B-01",
        "ownership_code": "OWN",
        "party_name": None,
        "unit_code": "KG",
        "source_quantity_kg": "20.000",
        "allocated_kg": "5.000",
        "current_source_stock_kg": "18.000",
        "unit_cost": None,
    }
    row.update(overrides)
    return row


class BabyConeSourcePreflightTests(unittest.TestCase):
    def test_available_quantity_is_limited_by_source_and_exact_dimension_stock(self):
        row = _baby_cone_source_rows([_source()])[0]
        self.assertEqual(row["available_kg"], Decimal("13.000"))
        self.assertTrue(row["eligible"])

    def test_party_source_without_captured_rate_is_blocked(self):
        row = _baby_cone_source_rows([
            _source(ownership_code="PARTY", party_name="Party A", unit_cost=None)
        ])[0]
        self.assertTrue(row["party_rate_missing"])
        self.assertFalse(row["eligible"])

    def test_party_source_with_captured_rate_can_pass_preflight(self):
        row = _baby_cone_source_rows([
            _source(ownership_code="PARTY", party_name="Party A", unit_cost="125.50")
        ])[0]
        self.assertFalse(row["party_rate_missing"])
        self.assertTrue(row["eligible"])
        self.assertEqual(row["unit_cost"], Decimal("125.50"))

    def test_exhausted_source_is_not_eligible(self):
        row = _baby_cone_source_rows([
            _source(allocated_kg="20.000", current_source_stock_kg="20.000")
        ])[0]
        self.assertEqual(row["available_kg"], Decimal("0"))
        self.assertFalse(row["eligible"])

    def test_stock_balance_shortfall_limits_available_quantity(self):
        row = _baby_cone_source_rows([
            _source(source_quantity_kg="20.000", allocated_kg="2.000",
                    current_source_stock_kg="4.000")
        ])[0]
        self.assertEqual(row["available_kg"], Decimal("2.000"))
        self.assertTrue(row["eligible"])


if __name__ == "__main__":
    unittest.main()
