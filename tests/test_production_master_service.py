import unittest
from decimal import Decimal
from app.production_master_service import _active, _text, _positive_id, _optional_decimal


class ProductionMasterValidationTests(unittest.TestCase):
    def test_active_accepts_boolean_and_form_values(self):
        self.assertTrue(_active("true"))
        self.assertFalse(_active("false"))
        self.assertFalse(_active(""))

    def test_active_rejects_ambiguous_values(self):
        with self.assertRaises(ValueError):
            _active("sometimes")

    def test_text_trims_and_upper_bound_is_enforced(self):
        self.assertEqual(_text("  Dyeing  ", "Name", 20), "Dyeing")
        with self.assertRaises(ValueError):
            _text("x" * 21, "Name", 20)

    def test_optional_text_can_be_blank(self):
        self.assertIsNone(_text("", "Description", 30, required=False))

    def test_positive_id_rejects_zero(self):
        with self.assertRaises(ValueError):
            _positive_id("0", "department")

    def test_optional_decimal_and_precision(self):
        self.assertEqual(_optional_decimal("1.250", "Capacity"), Decimal("1.250"))
        self.assertIsNone(_optional_decimal("", "Capacity"))
        with self.assertRaises(ValueError):
            _optional_decimal("1.2345", "Capacity")

    def test_negative_and_non_finite_capacity_rejected(self):
        for value in ("-1", "NaN", "Infinity"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _optional_decimal(value, "Capacity")


if __name__ == "__main__":
    unittest.main()
