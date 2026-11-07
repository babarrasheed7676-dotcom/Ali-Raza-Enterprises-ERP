import unittest
from decimal import Decimal

from app.big_cone_draft_service import normalize_big_cone_lines, _money


def _line(**overrides):
    value = {
        "source_dyeing_output_line_id": "21",
        "input_quantity_kg": "10.000",
        "output_quantity_kg": "9.750",
        "input_cones": "8",
        "output_cones": "8",
        "destination_type": "BABY_CONE",
    }
    value.update(overrides)
    return value


class BigConeDraftValidationTests(unittest.TestCase):
    def test_normalize_valid_line(self):
        rows = normalize_big_cone_lines([_line()])
        self.assertEqual(rows[0]["source_dyeing_output_line_id"], 21)
        self.assertEqual(rows[0]["input_quantity_kg"], Decimal("10.000"))
        self.assertEqual(rows[0]["output_quantity_kg"], Decimal("9.750"))
        self.assertEqual(rows[0]["destination_type"], "BABY_CONE")

    def test_reject_output_greater_than_input(self):
        with self.assertRaisesRegex(ValueError, "output cannot exceed"):
            normalize_big_cone_lines([_line(output_quantity_kg="10.001")])

    def test_reject_output_cones_greater_than_input_cones(self):
        with self.assertRaisesRegex(ValueError, "output cones cannot exceed"):
            normalize_big_cone_lines([_line(input_cones="0", output_cones="1")])

    def test_reject_duplicate_source_line(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            normalize_big_cone_lines([_line(), _line()])

    def test_reject_unknown_destination(self):
        with self.assertRaisesRegex(ValueError, "destination"):
            normalize_big_cone_lines([_line(destination_type="BABY_CONE_OR_NALKI")])

    def test_reject_more_than_three_kg_decimals(self):
        with self.assertRaisesRegex(ValueError, "3 decimal places"):
            normalize_big_cone_lines([_line(input_quantity_kg="1.0001")])

    def test_reject_negative_process_cost(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            _money("-1", "Labour cost")

    def test_reject_process_cost_with_excess_precision(self):
        with self.assertRaisesRegex(ValueError, "6 decimal places"):
            _money("1.0000001", "Labour cost")


if __name__ == "__main__":
    unittest.main()
