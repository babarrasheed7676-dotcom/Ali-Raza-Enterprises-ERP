import unittest
from datetime import date
from unittest.mock import patch

from app.dyeing_draft_service import (
    validate_dyeing_party_use_authorization,
    normalize_dyeing_yarn_io,
    normalize_dyeing_process_costs,
    create_dyeing_draft,
)


class DyeingPartyAuthorizationTests(unittest.TestCase):
    def test_own_material_remains_allowed(self):
        self.assertIsNone(validate_dyeing_party_use_authorization("OWN"))

    def test_party_material_can_be_captured_as_draft_pending_separate_request(self):
        self.assertIsNone(validate_dyeing_party_use_authorization("PARTY"))

    def test_unknown_ownership_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must be OWN or PARTY"):
            validate_dyeing_party_use_authorization("OTHER")


class DyeingYarnLineageValidationTests(unittest.TestCase):
    def _input(self, quantity="18.750000", variant="5423", batch=""):
        return {"item_variant_id": variant, "quantity_kg": quantity,
                "batch_id": batch, "notes": ""}

    def _output(self, source="1", consumed="18.750000", output="18.500000", shade="2701"):
        return {"source_line_no": source, "source_quantity_kg": consumed,
                "quantity_kg": output, "actual_shade_id": shade, "notes": ""}

    def test_valid_partial_source_allocation_is_normalized(self):
        inputs, outputs = normalize_dyeing_yarn_io(
            [self._input()],
            [self._output(consumed="10"), self._output(consumed="8.75", output="8.60", shade="2704")],
        )
        self.assertEqual(len(inputs), 1)
        self.assertEqual(len(outputs), 2)
        self.assertEqual(str(outputs[0]["source_quantity_kg"]), "10")
        self.assertEqual(str(outputs[1]["source_quantity_kg"]), "8.75")

    def test_output_source_consumption_cannot_exceed_input(self):
        with self.assertRaisesRegex(ValueError, "consume .* but only .* was entered"):
            normalize_dyeing_yarn_io(
                [self._input(quantity="10")],
                [self._output(consumed="6"), self._output(consumed="5", shade="2704")],
            )

    def test_output_requires_existing_input_line_and_shade(self):
        with self.assertRaisesRegex(ValueError, "source yarn line or shade is invalid"):
            normalize_dyeing_yarn_io([self._input()], [self._output(source="2")])

    def test_yarn_input_quantity_is_positive_and_stock_precision_is_three_decimal(self):
        with self.assertRaisesRegex(ValueError, "must be positive"):
            normalize_dyeing_yarn_io([self._input(quantity="0")], [self._output()])
        with self.assertRaisesRegex(ValueError, "maximum of 3 decimal places"):
            normalize_dyeing_yarn_io([self._input(quantity="1.0001")], [self._output()])


class DyeingProcessCostValidationTests(unittest.TestCase):
    def test_six_actual_cost_components_are_summed_exactly(self):
        result = normalize_dyeing_process_costs({
            "labour_cost": "1200.25", "machine_cost": "100",
            "electricity_cost": "250.50", "water_cost": "50",
            "boiler_fuel_cost": "80.25", "drying_cost": "40",
        })
        self.assertEqual(result["total_process_cost"], __import__("decimal").Decimal("1721.00"))
        self.assertEqual(result["labour_cost"], __import__("decimal").Decimal("1200.25"))

    def test_missing_process_cost_values_are_zero_without_inference(self):
        result = normalize_dyeing_process_costs({})
        self.assertEqual(result["total_process_cost"], __import__("decimal").Decimal("0"))
        self.assertTrue(all(result[key] == 0 for key in (
            "labour_cost","machine_cost","electricity_cost","water_cost","boiler_fuel_cost","drying_cost"
        )))

    def test_negative_or_nonfinite_process_cost_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            normalize_dyeing_process_costs({"labour_cost": "-1"})
        with self.assertRaisesRegex(ValueError, "non-negative"):
            normalize_dyeing_process_costs({"electricity_cost": "NaN"})

    def test_process_cost_precision_is_six_decimal_places(self):
        with self.assertRaisesRegex(ValueError, "maximum of 6 decimal places"):
            normalize_dyeing_process_costs({"water_cost": "1.0000001"})


class DyeingConsumptionSourceLineTests(unittest.TestCase):
    def _common(self, source_line_no=None):
        line = {
            "item_variant_id": "5425", "batch_id": "",
            "quantity": "0.100", "unit_id": "1",
            "ownership_type_id": "1", "owner_party_id": "",
            "notes": "synthetic",
        }
        if source_line_no is not None:
            line["source_line_no"] = source_line_no
        return {
            "company_id": 1,
            "user": {"id": 1, "company_id": 1},
            "request": None,
            "dyeing_date": date(2026, 11, 7),
            "remarks": "synthetic validation only",
            "lines": [line],
            "material_lines": [{
                "item_variant_id": "5423", "batch_id": "",
                "quantity_kg": "1.000", "notes": "synthetic",
            }],
            "output_lines": [{
                "source_line_no": "1", "source_quantity_kg": "1.000",
                "quantity_kg": "0.980", "actual_shade_id": "2701", "notes": "synthetic",
            }],
        }

    def test_missing_yarn_source_is_rejected_before_database_access(self):
        with patch("app.dyeing_draft_service.get_connection") as get_conn:
            with self.assertRaisesRegex(ValueError, "select the raw-Yarn input line"):
                create_dyeing_draft(**self._common())
            get_conn.assert_not_called()

    def test_unknown_yarn_source_line_is_rejected_before_database_access(self):
        with patch("app.dyeing_draft_service.get_connection") as get_conn:
            with self.assertRaisesRegex(ValueError, "not part of this Dyeing order"):
                create_dyeing_draft(**self._common(source_line_no="2"))
            get_conn.assert_not_called()


if __name__ == "__main__":
    unittest.main()
