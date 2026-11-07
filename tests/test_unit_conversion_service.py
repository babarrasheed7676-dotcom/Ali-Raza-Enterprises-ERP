import unittest
from datetime import date
from decimal import Decimal

from app.unit_conversion_service import (
    convert_unit_quantity,
    resolve_approved_unit_conversion,
    unit_conversion_key,
)


class UnitConversionKeyTests(unittest.TestCase):
    def test_key_is_directional_and_normalized(self):
        self.assertEqual(unit_conversion_key("kg", "gram"), "KG-TO-GRAM")
        self.assertNotEqual(unit_conversion_key("kg", "gram"), unit_conversion_key("gram", "kg"))

    def test_same_or_missing_units_are_rejected(self):
        for source, target in (("PCS", "PCS"), ("", "PCS"), ("PCS", "")):
            with self.subTest(source=source, target=target):
                with self.assertRaises(ValueError):
                    unit_conversion_key(source, target)


class UnitConversionArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "from_unit_code": "BOX",
            "to_unit_code": "PCS",
            "factor": "10",
            "rounding_places": 3,
            "rounding_mode": "ROUND_HALF_UP",
        }

    def test_exact_directed_conversion(self):
        result = convert_unit_quantity("2.5", self.snapshot)
        self.assertEqual(result["source_quantity"], Decimal("2.5"))
        self.assertEqual(result["unrounded_target_quantity"], Decimal("25.0"))
        self.assertEqual(result["target_quantity"], Decimal("25.000"))
        self.assertEqual(result["source_unit_code"], "BOX")
        self.assertEqual(result["target_unit_code"], "PCS")

    def test_half_up_rounding_is_explicit(self):
        snap = dict(self.snapshot, factor="0.333333", rounding_places=2)
        result = convert_unit_quantity("1", snap)
        self.assertEqual(result["target_quantity"], Decimal("0.33"))
        snap = dict(self.snapshot, factor="0.335", rounding_places=2)
        result = convert_unit_quantity("1", snap)
        self.assertEqual(result["target_quantity"], Decimal("0.34"))

    def test_negative_zero_nan_and_infinity_rejected(self):
        for value in ("-1", "0", "NaN", "Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    convert_unit_quantity(value, self.snapshot)

    def test_invalid_factor_rejected(self):
        for factor in ("0", "-2", "NaN", "Infinity"):
            with self.subTest(factor=factor):
                with self.assertRaises(ValueError):
                    convert_unit_quantity("1", dict(self.snapshot, factor=factor))

    def test_rounding_precision_cannot_exceed_stock_quantity_scale(self):
        with self.assertRaisesRegex(ValueError, "target quantity precision"):
            convert_unit_quantity("1", dict(self.snapshot, rounding_places=4), max_quantity_places=3)

    def test_600_milligrams_converts_exactly_to_0000600_kg_at_six_places(self):
        snap = {
            "from_unit_code": "MG",
            "to_unit_code": "KG",
            "factor": "0.000001",
            "rounding_places": 6,
            "rounding_mode": "ROUND_HALF_UP",
        }
        result = convert_unit_quantity("600", snap, max_quantity_places=6)
        self.assertEqual(result["source_quantity"], Decimal("600"))
        self.assertEqual(result["target_quantity"], Decimal("0.000600"))
        self.assertEqual(result["target_unit_code"], "KG")

    def test_mg_conversion_is_rejected_when_target_stock_precision_is_only_three(self):
        snap = {
            "from_unit_code": "MG", "to_unit_code": "KG",
            "factor": "0.000001", "rounding_places": 6,
            "rounding_mode": "ROUND_HALF_UP",
        }
        with self.assertRaisesRegex(ValueError, "target quantity precision"):
            convert_unit_quantity("600", snap, max_quantity_places=3)

    def test_conversion_that_rounds_to_zero_is_blocked(self):
        snap = dict(self.snapshot, factor="0.0001", rounding_places=3)
        with self.assertRaisesRegex(ValueError, "rounds to zero"):
            convert_unit_quantity("1", snap)

    def test_malformed_or_same_unit_snapshot_rejected(self):
        for snap in (
            dict(self.snapshot, to_unit_code="BOX"),
            dict(self.snapshot, from_unit_code=""),
            dict(self.snapshot, rounding_mode="ROUND_DOWN"),
        ):
            with self.subTest(snapshot=snap):
                with self.assertRaises(ValueError):
                    convert_unit_quantity("1", snap)


class UnitConversionResolverTests(unittest.TestCase):
    class Cursor:
        def __init__(self, responses):
            self.responses = list(responses)
            self.calls = []
        def execute(self, query, params):
            self.calls.append((query, params))
        def fetchall(self):
            return self.responses.pop(0)

    def payload(self):
        return {
            "effective_from": "2026-11-01",
            "from_unit_code": "BOX",
            "to_unit_code": "PCS",
            "factor": "10",
            "rounding_places": 3,
            "active": True,
        }

    def test_resolves_one_approved_exact_direction_and_active_units(self):
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS",
              "payload": self.payload(), "effective_from": date(2026,11,1),
              "effective_to": None}],
            [{"code": "BOX", "unit_type": "QUANTITY"}, {"code": "PCS", "unit_type": "QUANTITY"}],
        ])
        snap = resolve_approved_unit_conversion(
            cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
            effective_on=date(2026,11,5),
        )
        self.assertEqual(snap["configuration_version_id"], 81)
        self.assertEqual(snap["source"], "APPROVED_VERSION")
        self.assertEqual(snap["factor"], Decimal("10"))
        self.assertEqual(snap["rounding_mode"], "ROUND_HALF_UP")

    def test_missing_conversion_is_not_guessed_or_reversed(self):
        cur = self.Cursor([[]])
        with self.assertRaisesRegex(ValueError, "No approved effective"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="PCS", to_unit_code="BOX",
                effective_on=date(2026,11,5),
            )

    def test_duplicate_approved_conversions_block(self):
        rows = [{"id": 81}, {"id": 82}]
        cur = self.Cursor([rows])
        with self.assertRaisesRegex(RuntimeError, "Multiple approved"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_inactive_conversion_blocked(self):
        payload = dict(self.payload(), active=False)
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS", "payload": payload,
              "effective_from": date(2026,11,1), "effective_to": None}]
        ])
        with self.assertRaisesRegex(ValueError, "inactive"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_wrong_payload_direction_blocked(self):
        payload = dict(self.payload(), to_unit_code="GRAM")
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS", "payload": payload,
              "effective_from": date(2026,11,1), "effective_to": None}]
        ])
        with self.assertRaisesRegex(ValueError, "target unit"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_inactive_master_unit_blocked(self):
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS",
              "payload": self.payload(), "effective_from": date(2026,11,1),
              "effective_to": None}],
            [{"code": "BOX", "unit_type": "QUANTITY"}],
        ])
        with self.assertRaisesRegex(ValueError, "[Bb]oth source and target"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_different_physical_dimensions_are_rejected(self):
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS",
              "payload": self.payload(), "effective_from": date(2026,11,1),
              "effective_to": None}],
            [{"code": "BOX", "unit_type": "QUANTITY"}, {"code": "PCS", "unit_type": "WEIGHT"}],
        ])
        with self.assertRaisesRegex(ValueError, "dimensions do not match"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_payload_end_date_must_match_approved_version(self):
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS",
              "payload": dict(self.payload(), effective_to="2026-12-31"),
              "effective_from": date(2026,11,1), "effective_to": None}],
            [{"code": "BOX", "unit_type": "QUANTITY"}, {"code": "PCS", "unit_type": "QUANTITY"}],
        ])
        with self.assertRaisesRegex(ValueError, "end date"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )

    def test_payload_effective_date_must_match_approved_version(self):
        cur = self.Cursor([
            [{"id": 81, "config_key": "BOX-TO-PCS",
              "payload": dict(self.payload(), effective_from="2026-10-01"),
              "effective_from": date(2026,11,1), "effective_to": None}]
        ])
        with self.assertRaisesRegex(ValueError, "effective date"):
            resolve_approved_unit_conversion(
                cur, company_id=1, from_unit_code="BOX", to_unit_code="PCS",
                effective_on=date(2026,11,5),
            )


if __name__ == "__main__":
    unittest.main()
