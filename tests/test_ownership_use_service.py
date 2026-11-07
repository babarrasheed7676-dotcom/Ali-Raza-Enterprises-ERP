import unittest
from decimal import Decimal

from app.ownership_use_service import MODULE_TABLES, _positive_rate, _validate_request_unit_id, build_ownership_cost_snapshot


class OwnershipUseRateTests(unittest.TestCase):
    def test_supported_modules_resolve_expected_policy_and_quantity_column(self):
        self.assertEqual(MODULE_TABLES["DYEING"][1:], ("quantity", "DYEING-OWNERSHIP"))
        self.assertEqual(MODULE_TABLES["PACKING"][1:], ("quantity_pieces", "NALKI-OWNERSHIP"))

    def test_positive_pkr_rate_is_normalized_as_decimal(self):
        self.assertEqual(_positive_rate("12.345600"), Decimal("12.345600"))

    def test_zero_negative_non_numeric_and_non_finite_rates_are_rejected(self):
        for value in ("0", "-1", "abc", "NaN", "Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _positive_rate(value)

    def test_approved_party_use_cost_snapshot_pins_rate_and_total(self):
        from datetime import datetime, timezone
        row = {
            "id": 7, "company_id": 1, "use_module": "DYEING",
            "target_line_id": 55, "ownership_policy_version_id": 12,
            "owner_party_id": 9, "requested_quantity": Decimal("2.500000"),
            "unit_id": 4, "currency_code": "PKR",
            "locked_unit_rate": Decimal("120.000000"), "status": "APPROVED",
            "requested_by": 3, "decided_by": 4,
            "decided_at": datetime(2026, 11, 6, tzinfo=timezone.utc),
        }
        snapshot = build_ownership_cost_snapshot(
            row, snapshot_at=datetime(2026, 11, 6, 1, tzinfo=timezone.utc)
        )
        self.assertEqual(snapshot["locked_unit_rate"], "120.000000")
        self.assertEqual(snapshot["total_cost"], "300.000000")
        self.assertEqual(snapshot["ownership_policy_version_id"], 12)
        self.assertEqual(snapshot["request_id"], 7)

    def test_cost_snapshot_rounds_half_up_to_database_scale(self):
        from datetime import datetime, timezone
        row = {
            "id": 8, "company_id": 1, "use_module": "DYEING",
            "target_line_id": 56, "ownership_policy_version_id": 12,
            "owner_party_id": 9, "requested_quantity": Decimal("1.000001"),
            "unit_id": 4, "currency_code": "PKR",
            "locked_unit_rate": Decimal("0.500000"), "status": "APPROVED",
            "requested_by": 3, "decided_by": 4,
            "decided_at": datetime(2026, 11, 6, tzinfo=timezone.utc),
        }
        snapshot = build_ownership_cost_snapshot(row, snapshot_at="2026-11-06")
        self.assertEqual(snapshot["total_cost"], "0.500001")

    def test_cost_snapshot_rejects_pending_or_unlocked_request(self):
        row = {"status":"PENDING","locked_unit_rate":None}
        with self.assertRaisesRegex(ValueError, "approved request"):
            build_ownership_cost_snapshot(row, snapshot_at="2026-11-06")

    def test_request_rate_unit_must_match_source_line_unit(self):
        _validate_request_unit_id(4, 4)
        _validate_request_unit_id(None, None)
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            _validate_request_unit_id(5, 4)
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            _validate_request_unit_id(4, None)
        with self.assertRaisesRegex(ValueError, "must exactly match"):
            _validate_request_unit_id(None, 4)

    def test_rate_precision_is_limited_to_six_decimal_places(self):
        with self.assertRaisesRegex(ValueError, "maximum of 6 decimal places"):
            _positive_rate("1.0000001")


if __name__ == "__main__":
    unittest.main()
