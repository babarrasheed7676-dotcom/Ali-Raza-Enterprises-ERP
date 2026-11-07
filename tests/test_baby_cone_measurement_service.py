import unittest
from decimal import Decimal

from app.baby_cone_measurement_service import calculate_baby_cone_measurement


class BabyConeMeasurementCalculationTests(unittest.TestCase):
    def test_net_weight_and_grams_per_yard(self):
        result = calculate_baby_cone_measurement("120", "20", "500")
        self.assertEqual(result["net_yarn_grams"], Decimal("100"))
        self.assertEqual(result["grams_per_yard"], Decimal("0.2"))

    def test_required_yards_calculates_kg_without_early_rounding(self):
        result = calculate_baby_cone_measurement("120", "20", "500", "2500")
        self.assertEqual(result["required_yarn_kg"], Decimal("0.5"))
        self.assertEqual(result["required_yards"], Decimal("2500"))

    def test_zero_tare_is_valid(self):
        result = calculate_baby_cone_measurement("50", "0", "100")
        self.assertEqual(result["net_yarn_grams"], Decimal("50"))

    def test_gross_must_exceed_tare(self):
        for gross, tare in (("20", "20"), ("10", "20")):
            with self.subTest(gross=gross, tare=tare):
                with self.assertRaisesRegex(ValueError, "must exceed"):
                    calculate_baby_cone_measurement(gross, tare, "100")

    def test_invalid_nonpositive_or_nonfinite_values_rejected(self):
        for values in (
            ("0", "0", "100"), ("100", "-1", "100"),
            ("100", "0", "0"), ("NaN", "0", "100"),
            ("Infinity", "0", "100"), ("100", "0", "NaN"),
        ):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    calculate_baby_cone_measurement(*values)

    def test_required_yards_must_be_positive_and_finite(self):
        for yards in ("0", "-1", "NaN", "Infinity"):
            with self.subTest(yards=yards):
                with self.assertRaises(ValueError):
                    calculate_baby_cone_measurement("100", "10", "100", yards)


if __name__ == "__main__":
    unittest.main(verbosity=2)


class BabyConeMeasurementProfileCalculationTests(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "config_type": "MEASUREMENT_PROFILE",
            "configuration_version_id": 81,
            "payload": {
                "profile_code": "BABY-CONE-GPY",
                "variant_code": "BC-20",
                "method": "weight_per_length",
                "tolerance_percent": "2.5",
                "requires_operator": True,
                "requires_approval": True,
                "active": True,
            },
        }

    def calculate(self, **kwargs):
        from app.baby_cone_measurement_service import calculate_baby_cone_profile_measurement
        args = {
            "profile_snapshot": self.profile,
            "gross_weight_grams": "120",
            "empty_core_tare_grams": "20",
            "measured_yards": "500",
            "operator_code": "OP-01",
            "required_yards": "2500",
        }
        args.update(kwargs)
        return calculate_baby_cone_profile_measurement(**args)

    def test_approved_profile_is_carried_into_calculation(self):
        result = self.calculate()
        self.assertEqual(result["net_yarn_grams"], Decimal("100"))
        self.assertEqual(result["grams_per_yard"], Decimal("0.2"))
        self.assertEqual(result["required_yarn_kg"], Decimal("0.5"))
        self.assertEqual(result["configuration_version_id"], 81)
        self.assertEqual(result["variant_code"], "BC-20")
        self.assertTrue(result["requires_approval"])
        self.assertEqual(result["tolerance_percent"], Decimal("2.5"))

    def test_required_operator_is_enforced(self):
        with self.assertRaisesRegex(ValueError, "requires an operator"):
            self.calculate(operator_code="")

    def test_profile_must_be_approved_version_snapshot(self):
        invalid = dict(self.profile, configuration_version_id=None)
        with self.assertRaisesRegex(ValueError, "version is missing"):
            self.calculate(profile_snapshot=invalid)

    def test_inactive_or_wrong_method_profile_fails_closed(self):
        invalid = {"config_type": "MEASUREMENT_PROFILE", "configuration_version_id": 81,
                   "payload": dict(self.profile["payload"], active=False)}
        with self.assertRaisesRegex(ValueError, "active weight_per_length"):
            self.calculate(profile_snapshot=invalid)

    def test_profile_type_must_match(self):
        invalid = dict(self.profile, config_type="BABY_CONE_MEASUREMENT")
        with self.assertRaisesRegex(ValueError, "Unsupported configuration"):
            self.calculate(profile_snapshot=invalid)
