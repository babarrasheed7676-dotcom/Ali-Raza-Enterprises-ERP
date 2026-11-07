import unittest
from datetime import date
from decimal import Decimal

from app.dyeing_conversion_service import build_dyeing_unit_conversion_snapshot


class Cursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))

    def fetchall(self):
        return self.responses.pop(0)


class DyeingConversionSnapshotTests(unittest.TestCase):
    def test_same_base_unit_needs_no_conversion(self):
        cur = Cursor([])
        result = build_dyeing_unit_conversion_snapshot(
            cur, company_id=1, effective_on=date(2026, 11, 7),
            source_quantity=Decimal("12.500000"),
            source_unit_code="KG", target_unit_code="KG",
            target_decimal_places=3,
        )
        self.assertEqual(result["status"], "NOT_REQUIRED")
        self.assertEqual(result["converted_quantity"], Decimal("12.500000"))
        self.assertEqual(result["conversion_factor"], Decimal("1"))
        self.assertEqual(result["snapshot"]["factor"], "1")
        self.assertEqual(result["snapshot"]["rounding_mode"], "ROUND_HALF_UP")
        self.assertIsNone(result["configuration_version_id"])
        self.assertEqual(cur.calls, [])

    def test_missing_approved_rule_is_saved_as_pending_not_guessed(self):
        cur = Cursor([[]])
        result = build_dyeing_unit_conversion_snapshot(
            cur, company_id=1, effective_on=date(2026, 11, 7),
            source_quantity=Decimal("600"),
            source_unit_code="MG", target_unit_code="KG",
            target_decimal_places=3,
        )
        self.assertEqual(result["status"], "PENDING_CONFIGURATION")
        self.assertIsNone(result["converted_quantity"])
        self.assertIsNone(result["configuration_version_id"])
        self.assertIsNone(result["conversion_factor"])
        self.assertEqual(result["snapshot"]["source"], "NO_APPROVED_EFFECTIVE_RULE")
        self.assertEqual(result["snapshot"]["rounding_mode"], "ROUND_HALF_UP")

    def approved_cursor(self, places=3):
        payload = {
            "effective_from": "2026-11-01",
            "from_unit_code": "BOX",
            "to_unit_code": "PCS",
            "factor": "10",
            "rounding_places": places,
            "active": True,
        }
        return Cursor([
            [{
                "id": 91, "config_key": "BOX-TO-PCS",
                "payload": payload, "effective_from": date(2026, 11, 1),
                "effective_to": None,
            }],
            [{"code": "BOX", "unit_type": "QUANTITY"}, {"code": "PCS", "unit_type": "QUANTITY"}],
        ])

    def test_approved_rule_is_pinned_and_calculated(self):
        cur = self.approved_cursor(3)
        result = build_dyeing_unit_conversion_snapshot(
            cur, company_id=1, effective_on=date(2026, 11, 7),
            source_quantity=Decimal("2.500000"),
            source_unit_code="BOX", target_unit_code="PCS",
            target_decimal_places=3,
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertEqual(result["configuration_version_id"], 91)
        self.assertEqual(result["converted_quantity"], Decimal("25.000"))
        self.assertEqual(result["snapshot"]["factor"], "10")

    def test_approved_rule_exceeding_base_precision_is_blocked(self):
        cur = self.approved_cursor(6)
        result = build_dyeing_unit_conversion_snapshot(
            cur, company_id=1, effective_on=date(2026, 11, 7),
            source_quantity=Decimal("2.500000"),
            source_unit_code="BOX", target_unit_code="PCS",
            target_decimal_places=3,
        )
        self.assertEqual(result["status"], "BLOCKED_PRECISION")
        self.assertIsNone(result["converted_quantity"])
        self.assertEqual(result["configuration_version_id"], 91)
        self.assertEqual(result["snapshot"]["unrounded_target_quantity"], "25.000000")

    def test_wrong_direction_or_malformed_rule_is_not_silently_pending(self):
        cur = Cursor([[
            {
                "id": 91, "config_key": "BOX-TO-PCS",
                "payload": {
                    "effective_from": "2026-11-01",
                    "from_unit_code": "PCS", "to_unit_code": "BOX",
                    "factor": "0.1", "rounding_places": 3, "active": True,
                },
                "effective_from": date(2026, 11, 1), "effective_to": None,
            }
        ]])
        with self.assertRaisesRegex(ValueError, "source unit"):
            build_dyeing_unit_conversion_snapshot(
                cur, company_id=1, effective_on=date(2026, 11, 7),
                source_quantity=Decimal("2"),
                source_unit_code="BOX", target_unit_code="PCS",
                target_decimal_places=3,
            )


if __name__ == "__main__":
    unittest.main()